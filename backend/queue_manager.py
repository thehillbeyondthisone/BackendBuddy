from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid
import asyncio
import logging
import traceback

# Set up logging
logger = logging.getLogger("BackendBuddy.QueueManager")


@dataclass
class QueueUser:
    """Represents a user in the queue"""
    session_id: str
    joined_at: datetime
    last_heartbeat: datetime
    position: int
    is_active: bool = False
    is_localhost: bool = False


class QueueManager:
    """Manages the waiting room queue for remote users"""
    
    def __init__(self):
        self.active_users: List[QueueUser] = []
        self.waiting_users: List[QueueUser] = []
        self.heartbeat_timeout = 30  # seconds
        self.max_concurrent = 1  # default, updated from config
        self.prioritize_localhost = True  # default, updated from config
        self.callbacks = []  # WebSocket callbacks for queue updates
        logger.debug("QueueManager initialized")
    
    def configure(self, max_concurrent: int = 1, prioritize_localhost: bool = True):
        """Update queue settings from config"""
        self.max_concurrent = max(1, max_concurrent)
        self.prioritize_localhost = prioritize_localhost
        logger.info(f"QueueManager configured: max_concurrent={self.max_concurrent}, prioritize_localhost={self.prioritize_localhost}")
        
    def add_callback(self, callback):
        """Add a callback for queue updates"""
        self.callbacks.append(callback)
        logger.debug(f"Added callback, total callbacks: {len(self.callbacks)}")
    
    def remove_callback(self, callback):
        """Remove a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Removed callback, total callbacks: {len(self.callbacks)}")
    
    async def notify_all(self):
        """Notify all callbacks of queue state change"""
        state = self.get_queue_state()
        logger.debug(f"Notifying {len(self.callbacks)} callbacks of state change")
        for callback in self.callbacks:
            try:
                await callback(state)
            except Exception as e:
                logger.error(f"Callback notification failed: {e}")
    
    def _is_user_active(self, session_id: str) -> bool:
        """Check if a session is in the active users list"""
        return any(u.session_id == session_id for u in self.active_users)
    
    def _get_active_user(self, session_id: str) -> Optional[QueueUser]:
        """Get an active user by session_id"""
        for u in self.active_users:
            if u.session_id == session_id:
                return u
        return None
    
    def join_queue(self, session_id: Optional[str] = None, is_localhost: bool = False) -> Dict:
        """Add a user to the queue or grant immediate access"""
        logger.info(f"join_queue called with session_id: {session_id}, is_localhost: {is_localhost}")
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.debug(f"Generated new session_id: {session_id}")
        
        # Check if user is already active
        if self._is_user_active(session_id):
            logger.debug(f"User {session_id} is already active")
            return {
                "session_id": session_id,
                "status": "active",
                "position": 0,
                "message": "Already active"
            }
        
        # Check if user already in waiting queue
        for user in self.waiting_users:
            if user.session_id == session_id:
                logger.debug(f"User {session_id} already in queue at position {user.position}")
                return {
                    "session_id": session_id,
                    "status": "waiting",
                    "position": user.position,
                    "queue_length": len(self.waiting_users),
                    "message": "Already in queue"
                }
        
        now = datetime.utcnow()
        
        # Localhost priority: grant immediate access if enabled
        if is_localhost and self.prioritize_localhost:
            logger.info(f"Localhost user {session_id} granted priority access")
            new_user = QueueUser(
                session_id=session_id,
                joined_at=now,
                last_heartbeat=now,
                position=0,
                is_active=True,
                is_localhost=True
            )
            self.active_users.append(new_user)
            self._try_notify()
            return {
                "session_id": session_id,
                "status": "active",
                "position": 0,
                "message": "Localhost priority access granted"
            }
        
        # Check if there's room in the active pool
        if len(self.active_users) < self.max_concurrent:
            logger.info(f"Active pool has room, granting access to {session_id}")
            new_user = QueueUser(
                session_id=session_id,
                joined_at=now,
                last_heartbeat=now,
                position=0,
                is_active=True,
                is_localhost=is_localhost
            )
            self.active_users.append(new_user)
            self._try_notify()
            return {
                "session_id": session_id,
                "status": "active",
                "position": 0,
                "message": "Access granted"
            }
        
        # Add to waiting queue
        position = len(self.waiting_users) + 1
        logger.info(f"Adding user {session_id} to queue at position {position}")
        user = QueueUser(
            session_id=session_id,
            joined_at=now,
            last_heartbeat=now,
            position=position,
            is_active=False,
            is_localhost=is_localhost
        )
        self.waiting_users.append(user)
        self._update_positions()
        self._try_notify()
        
        return {
            "session_id": session_id,
            "status": "waiting",
            "position": position,
            "queue_length": len(self.waiting_users),
            "message": f"Added to queue at position {position}"
        }
    
    def leave_queue(self, session_id: str) -> Dict:
        """Remove a user from the queue"""
        logger.info(f"leave_queue called for session_id: {session_id}")
        
        # Check if in active users
        for i, user in enumerate(self.active_users):
            if user.session_id == session_id:
                logger.info(f"Active user {session_id} is leaving")
                self.active_users.pop(i)
                self._promote_waiting_users()
                self._try_notify()
                return {"success": True, "message": "Left active session"}
        
        # Check waiting users
        for i, user in enumerate(self.waiting_users):
            if user.session_id == session_id:
                logger.info(f"Removing waiting user {session_id} from position {user.position}")
                self.waiting_users.pop(i)
                self._update_positions()
                self._try_notify()
                return {"success": True, "message": "Removed from queue"}
        
        logger.warning(f"Session {session_id} not found in queue")
        return {"success": False, "message": "Session not found"}
    
    def heartbeat(self, session_id: str) -> Dict:
        """Update heartbeat for a user"""
        now = datetime.utcnow()
        
        # Check active users
        for user in self.active_users:
            if user.session_id == session_id:
                user.last_heartbeat = now
                logger.debug(f"Heartbeat received from active user {session_id}")
                return {"success": True, "status": "active", "position": 0}
        
        # Check waiting users
        for user in self.waiting_users:
            if user.session_id == session_id:
                user.last_heartbeat = now
                logger.debug(f"Heartbeat received from waiting user {session_id} at position {user.position}")
                return {
                    "success": True, 
                    "status": "waiting", 
                    "position": user.position,
                    "queue_length": len(self.waiting_users)
                }
        
        logger.warning(f"Heartbeat from unknown session: {session_id}")
        return {"success": False, "message": "Session not found"}
    
    def check_timeouts(self):
        """Remove users who haven't sent heartbeat - prevents zombies"""
        now = datetime.utcnow()
        timeout_threshold = now - timedelta(seconds=self.heartbeat_timeout)
        
        # Check active users
        timed_out_active = []
        for user in self.active_users:
            if user.last_heartbeat < timeout_threshold:
                timed_out_active.append(user)
        
        for user in timed_out_active:
            logger.info(f"Active user {user.session_id} timed out (zombie cleanup)")
            self.active_users.remove(user)
        
        # Check waiting users
        timed_out_waiting = []
        for user in self.waiting_users:
            if user.last_heartbeat < timeout_threshold:
                timed_out_waiting.append(user)
        
        for user in timed_out_waiting:
            logger.info(f"Waiting user {user.session_id} at position {user.position} timed out")
            self.waiting_users.remove(user)
        
        if timed_out_active or timed_out_waiting:
            self._update_positions()
            self._promote_waiting_users()
            self._try_notify()
    
    def _promote_waiting_users(self):
        """Promote waiting users to active if there's room"""
        while len(self.active_users) < self.max_concurrent and self.waiting_users:
            next_user = self.waiting_users.pop(0)
            next_user.is_active = True
            next_user.position = 0
            self.active_users.append(next_user)
            logger.info(f"Promoted user {next_user.session_id} to active")
        self._update_positions()
    
    def _update_positions(self):
        """Update position numbers for all waiting users"""
        for i, user in enumerate(self.waiting_users):
            user.position = i + 1
        logger.debug(f"Updated positions for {len(self.waiting_users)} waiting users")
    
    def _try_notify(self):
        """Try to create a notify task, handle case where no event loop"""
        try:
            asyncio.create_task(self.notify_all())
        except Exception as e:
            logger.debug(f"Could not create notify task (may be sync context): {e}")
    
    def get_queue_state(self) -> Dict:
        """Get current queue state"""
        state = {
            "active_count": len(self.active_users),
            "max_concurrent": self.max_concurrent,
            "active_users": [u.session_id for u in self.active_users],
            "queue_length": len(self.waiting_users),
            "waiting_users": [
                {
                    "session_id": user.session_id,
                    "position": user.position,
                    "wait_time": int((datetime.utcnow() - user.joined_at).total_seconds())
                }
                for user in self.waiting_users
            ]
        }
        logger.debug(f"Queue state: active={state['active_count']}/{state['max_concurrent']}, waiting={state['queue_length']}")
        return state
    
    def get_user_status(self, session_id: str) -> Optional[Dict]:
        """Get status for a specific user"""
        # Check active users
        for user in self.active_users:
            if user.session_id == session_id:
                return {
                    "session_id": session_id,
                    "status": "active",
                    "position": 0
                }
        
        # Check waiting users
        for user in self.waiting_users:
            if user.session_id == session_id:
                return {
                    "session_id": session_id,
                    "status": "waiting",
                    "position": user.position,
                    "queue_length": len(self.waiting_users),
                    "estimated_wait": user.position * 30  # Rough estimate in seconds
                }
        
        return None


# Global queue manager instance
queue_manager = QueueManager()
logger.info("Global QueueManager instance created")
