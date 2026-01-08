from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import uuid
import logging
import traceback
import logging
import traceback
import sys
from contextlib import asynccontextmanager

# ===== LOGGING SETUP =====
import os
LOG_LEVEL = os.environ.get('BACKENDBUDDY_LOG_LEVEL', 'INFO').upper()
_log_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=_log_level,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BackendBuddy")
logger.setLevel(_log_level)

# Also configure uvicorn logger
logging.getLogger("uvicorn").setLevel(_log_level)
logging.getLogger("uvicorn.access").setLevel(_log_level)
logging.getLogger("uvicorn.error").setLevel(_log_level)

from database import init_db, get_db, ProjectConfig, ProjectPreset
from server_manager import server_manager
from queue_manager import queue_manager
from network_manager import network_manager
from traffic_monitor import traffic_monitor
import time as time_module

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture main event loop for thread-safe broadcasting
    global main_loop
    main_loop = asyncio.get_running_loop()
    
    # Startup: Start background tasks
    logger.info("Starting background tasks...")
    task = asyncio.create_task(queue_timeout_checker())
    logger.info("Background tasks started")
    yield
    # Shutdown: Cleanup
    logger.info("Shutting down Application...")
    try:
        # Cancel background task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        server_manager.stop()
        network_manager.stop_ngrok()
        network_manager.stop_cloudflare()
        logger.info("Server and ngrok/cloudflared stopped")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}")

# Initialize FastAPI app
app = FastAPI(title="BackendBuddy - Vibecoding Project Manager", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Traffic monitoring middleware
@app.middleware("http")
async def traffic_monitoring_middleware(request: Request, call_next):
    """Track all HTTP requests for traffic monitoring"""
    start_time = time_module.time()
    
    # Get request info
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # Get request body size (approximate)
    content_length = request.headers.get("content-length", "0")
    bytes_in = int(content_length) if content_length.isdigit() else 0
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    latency_ms = (time_module.time() - start_time) * 1000
    
    # Get response size (approximate)
    bytes_out = int(response.headers.get("content-length", 0))
    
    # Log to traffic monitor (skip traffic endpoints to avoid recursion)
    if not path.startswith("/api/traffic") and not path.startswith("/ws/traffic"):
        traffic_monitor.log_request(
            method=method,
            path=path,
            status=response.status_code,
            latency_ms=latency_ms,
            client_ip=client_ip,
            user_agent=user_agent,
            bytes_in=bytes_in,
            bytes_out=bytes_out
        )
    
    return response


# Initialize database
logger.info("Initializing database...")
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    logger.error(traceback.format_exc())
    raise

# Pydantic models
class ProjectConfigUpdate(BaseModel):
    name: Optional[str] = None
    directory: Optional[str] = None
    command: Optional[str] = None
    frontend_directory: Optional[str] = None
    frontend_command: Optional[str] = None
    port: Optional[int] = None
    lan_ip: Optional[str] = None
    lan_enabled: Optional[bool] = None
    ngrok_enabled: Optional[bool] = None
    cloudflare_enabled: Optional[bool] = None
    queue_enabled: Optional[bool] = None


class ServerCommand(BaseModel):
    action: str  # start, stop, restart


class QueueAction(BaseModel):
    session_id: Optional[str] = None


# WebSocket connections for logs
MAX_WS_CONNECTIONS = 10  # Limit to prevent resource exhaustion
log_connections: List[WebSocket] = []

# WebSocket connections for queue updates
queue_connections: List[WebSocket] = []

# WebSocket connections for traffic monitoring
traffic_connections: List[WebSocket] = []

# Global event loop reference
main_loop: Optional[asyncio.AbstractEventLoop] = None


# Middleware to check if user should be in waiting room
def is_local_request(request: Request) -> bool:
    """Check if request is from localhost"""
    client_host = request.client.host if request.client else ""
    is_local = client_host in ["127.0.0.1", "localhost", "::1"]
    logger.debug(f"Request from {client_host} - is_local: {is_local}")
    return is_local


# ===== EXCEPTION HANDLER =====

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all exceptions and log them"""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__}
    )


# ===== PROJECT CONFIG ENDPOINTS =====

@app.get("/api/config")
def get_config(db: Session = Depends(get_db)):
    """Get current project configuration"""
    logger.debug("GET /api/config called")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            logger.warning("No configuration found in database")
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        result = {
            "name": config.name,
            "directory": config.directory,
            "command": config.command,
            "frontend_directory": config.frontend_directory,
            "frontend_command": config.frontend_command,
            "port": config.port,
            "lan_ip": config.lan_ip,
            "lan_enabled": config.lan_enabled,
            "ngrok_enabled": config.ngrok_enabled,
            "cloudflare_enabled": getattr(config, "cloudflare_enabled", False),
            "queue_enabled": config.queue_enabled,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None
        }
        logger.debug(f"Returning config: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_config: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scan-project")
def scan_project_endpoint(path: str):
    """Scan a project directory for auto-configuration"""
    logger.info(f"Scanning project at: {path}")
    result = server_manager.scan_project(path)
    if not result.get("success", False):
         raise HTTPException(status_code=400, detail=result.get("message"))
    return result

@app.put("/api/config")
def update_config(update: ProjectConfigUpdate, db: Session = Depends(get_db)):
    """Update project configuration"""
    logger.info(f"PUT /api/config called with: {update.dict()}")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            logger.warning("No configuration found to update")
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Update fields
        if update.name is not None:
            logger.debug(f"Updating name: {config.name} -> {update.name}")
            config.name = update.name
        if update.directory is not None:
            logger.debug(f"Updating directory: {config.directory} -> {update.directory}")
            config.directory = update.directory
        if update.command is not None:
            logger.debug(f"Updating command: {config.command} -> {update.command}")
            config.command = update.command
        if update.frontend_directory is not None:
            logger.debug(f"Updating frontend_directory: {config.frontend_directory} -> {update.frontend_directory}")
            config.frontend_directory = update.frontend_directory
        if update.frontend_command is not None:
            logger.debug(f"Updating frontend_command: {config.frontend_command} -> {update.frontend_command}")
            config.frontend_command = update.frontend_command
        if update.port is not None:
            logger.debug(f"Updating port: {config.port} -> {update.port}")
            config.port = update.port
        if update.lan_ip is not None:
            logger.debug(f"Updating lan_ip: {config.lan_ip} -> {update.lan_ip}")
            config.lan_ip = update.lan_ip
        if update.lan_enabled is not None:
            logger.debug(f"Updating lan_enabled: {config.lan_enabled} -> {update.lan_enabled}")
            config.lan_enabled = update.lan_enabled
        if update.ngrok_enabled is not None:
            logger.debug(f"Updating ngrok_enabled: {config.ngrok_enabled} -> {update.ngrok_enabled}")
            config.ngrok_enabled = update.ngrok_enabled
            # Note: Tunnels are now started/stopped via dedicated buttons, not config save
        
        if update.cloudflare_enabled is not None:
            logger.debug(f"Updating cloudflare_enabled: {getattr(config, 'cloudflare_enabled', False)} -> {update.cloudflare_enabled}")
            config.cloudflare_enabled = update.cloudflare_enabled
            # Note: Tunnels are now started/stopped via dedicated buttons, not config save
        
        if update.queue_enabled is not None:
            logger.debug(f"Updating queue_enabled: {config.queue_enabled} -> {update.queue_enabled}")
            config.queue_enabled = update.queue_enabled
        
        db.commit()
        db.refresh(config)
        
        logger.info("Configuration updated successfully")
        return {"success": True, "message": "Configuration updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_config: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== PRESET ENDPOINTS =====

class PresetCreate(BaseModel):
    name: str

@app.get("/api/presets")
def list_presets(db: Session = Depends(get_db)):
    """List all saved presets"""
    logger.debug("GET /api/presets called")
    try:
        presets = db.query(ProjectPreset).all()
        return [{"id": p.id, "name": p.name, "directory": p.directory} for p in presets]
    except Exception as e:
        logger.error(f"Error listing presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/presets")
def save_preset(preset: PresetCreate, db: Session = Depends(get_db)):
    """Save current config as a preset"""
    logger.info(f"POST /api/presets - saving as '{preset.name}'")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            raise HTTPException(status_code=404, detail="No config to save")
        
        # Check if preset name exists
        existing = db.query(ProjectPreset).filter(ProjectPreset.name == preset.name).first()
        if existing:
            # Update existing
            existing.directory = config.directory
            existing.command = config.command
            existing.frontend_directory = config.frontend_directory
            existing.frontend_command = config.frontend_command
            existing.port = config.port
            db.commit()
            return {"success": True, "message": f"Preset '{preset.name}' updated"}
        
        # Create new
        new_preset = ProjectPreset(
            name=preset.name,
            directory=config.directory,
            command=config.command,
            frontend_directory=config.frontend_directory,
            frontend_command=config.frontend_command,
            port=config.port
        )
        db.add(new_preset)
        db.commit()
        return {"success": True, "message": f"Preset '{preset.name}' saved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/presets/{preset_id}/load")
def load_preset(preset_id: int, db: Session = Depends(get_db)):
    """Load a preset into current config"""
    logger.info(f"POST /api/presets/{preset_id}/load")
    try:
        preset = db.query(ProjectPreset).filter(ProjectPreset.id == preset_id).first()
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        config = db.query(ProjectConfig).first()
        if not config:
            raise HTTPException(status_code=404, detail="No config found")
        
        config.name = preset.name
        config.directory = preset.directory
        config.command = preset.command
        config.frontend_directory = preset.frontend_directory
        config.frontend_command = preset.frontend_command
        config.port = preset.port
        db.commit()
        
        return {"success": True, "message": f"Loaded preset '{preset.name}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    """Delete a preset"""
    logger.info(f"DELETE /api/presets/{preset_id}")
    try:
        preset = db.query(ProjectPreset).filter(ProjectPreset.id == preset_id).first()
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        name = preset.name
        db.delete(preset)
        db.commit()
        return {"success": True, "message": f"Deleted preset '{name}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== SERVER CONTROL ENDPOINTS =====

@app.post("/api/server")
def control_server(command: ServerCommand, db: Session = Depends(get_db)):
    """Control the dev server"""
    logger.info(f"POST /api/server called with action: {command.action}")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            logger.warning("No configuration found")
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        logger.debug(f"Config: directory={config.directory}, command={config.command}, port={config.port}")
        
        if not config.directory or not config.command:
            logger.warning("Server directory or command not configured")
            raise HTTPException(status_code=400, detail="Server directory and command must be configured")
        
        if command.action == "start":
            logger.info(f"Starting server in {config.directory} with command: {config.command}")
            
            # Safety: Skip frontend if same directory as backend (prevents port collision)
            frontend_dir = config.frontend_directory
            frontend_cmd = config.frontend_command
            if frontend_dir and config.directory and os.path.normpath(frontend_dir) == os.path.normpath(config.directory):
                logger.warning(f"Frontend directory same as backend - skipping frontend to prevent port collision")
                frontend_dir = None
                frontend_cmd = None
            
            result = server_manager.start(
                config.directory,
                config.command,
                frontend_dir,
                frontend_cmd,
                log_callback=broadcast_log
            )
            logger.info(f"Start result: {result}")
            
            # Links are now initialized separately via /api/links/init
            # No longer auto-starting tunnels with server
            
            return result
        
        elif command.action == "stop":
            logger.info("Stopping server")
            result = server_manager.stop()
            logger.info(f"Stop result: {result}")
            
            # Note: We do NOT stop ngrok/cloudflare here to allow persistent links
            # Tunnels are only stopped on application shutdown
            
            return result
        
        elif command.action == "restart":
            logger.info("Restarting server")
            
            # Do NOT stop tunnels on restart, keep them alive for persistence
            
            result = server_manager.restart(
                config.directory,
                config.command,
                config.frontend_directory,
                config.frontend_command
            )
            logger.info(f"Restart result: {result}")
            
            # Ensure tunnels are running if they should be (in case they crashed or weren't running)
            if result["success"]:
                try:
                    if config.ngrok_enabled and config.port:
                        ngrok_status = network_manager.get_ngrok_status()
                        if not ngrok_status["running"]:
                            logger.info(f"Starting ngrok on port {config.port} (was not running)")
                            ngrok_result = network_manager.start_ngrok(config.port)
                            if not ngrok_result["success"]:
                                logger.warning(f"ngrok warning: {ngrok_result['message']}")
                        else:
                            logger.info("ngrok tunnel persisted")

                    if getattr(config, "cloudflare_enabled", False) and config.port:
                        # Check if cloudflare is running
                        if not network_manager.cloudflare_process:
                            logger.info(f"Starting cloudflared on port {config.port} (was not running)")
                            cf_result = network_manager.start_cloudflare(config.port)
                            if not cf_result["success"]:
                                logger.warning(f"cloudflared warning: {cf_result['message']}")
                        else:
                             logger.info("cloudflared tunnel persisted")
                except Exception as e:
                    logger.error(f"Error restoring tunnels after restart: {e}")
            
            return result
            
            return result
        
        else:
            logger.warning(f"Invalid action: {command.action}")
            raise HTTPException(status_code=400, detail="Invalid action")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in control_server: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/server/status")
def get_server_status():
    """Get server status"""
    logger.debug("GET /api/server/status called")
    try:
        status = server_manager.get_status()
        logger.debug(f"Server status: {status}")
        return status
    except Exception as e:
        logger.error(f"Error in get_server_status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/server/logs")
def get_logs():
    """Get recent server logs"""
    logger.debug("GET /api/server/logs called")
    try:
        logs = server_manager.get_recent_logs()
        logger.debug(f"Returning {len(logs)} log entries")
        return {"logs": logs}
    except Exception as e:
        logger.error(f"Error in get_logs: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== NETWORK/LINKS ENDPOINTS =====

@app.get("/api/links")
def get_links(db: Session = Depends(get_db)):
    """Get all access links with auto-detected LAN IPs"""
    logger.debug("GET /api/links called")
    try:
        config = db.query(ProjectConfig).first()
        if not config or not config.port:
            logger.debug("No config or port, returning empty links")
            return {"links": {}, "lan_ips": []}
        
        # Auto-detect LAN IPs
        lan_ips = network_manager.get_lan_ips()
        
        # Generate base links
        links = {
            "localhost": f"http://localhost:{config.port}",
            "lan": [],  # Now an array of all LAN links
            "ngrok": None,
            "cloudflare": None
        }
        
        # Add all LAN links if LAN is enabled
        if config.lan_enabled and lan_ips:
            links["lan"] = [f"http://{ip}:{config.port}" for ip in lan_ips]
        
        # Add ngrok link if enabled
        if config.ngrok_enabled and network_manager.ngrok_url:
            links["ngrok"] = network_manager.ngrok_url
            
        # Add cloudflare link if enabled
        if getattr(config, "cloudflare_enabled", False) and network_manager.cloudflare_url:
            links["cloudflare"] = network_manager.cloudflare_url
        
        logger.debug(f"Generated links: {links}")
        
        return {"links": links, "lan_ips": lan_ips}
    except Exception as e:
        logger.error(f"Error in get_links: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/network/lan-ips")
def get_lan_ips():
    """Get auto-detected LAN IP addresses"""
    logger.debug("GET /api/network/lan-ips called")
    try:
        ips = network_manager.get_lan_ips()
        return {"lan_ips": ips}
    except Exception as e:
        logger.error(f"Error in get_lan_ips: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== TUNNEL CONTROL ENDPOINTS =====

class TunnelAction(BaseModel):
    action: str  # start, stop

@app.post("/api/ngrok")
def control_ngrok(action: TunnelAction, db: Session = Depends(get_db)):
    """Start or stop ngrok tunnel"""
    logger.info(f"POST /api/ngrok called with action: {action.action}")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        if action.action == "start":
            if config.port:
                result = network_manager.start_ngrok(config.port)
                logger.info(f"ngrok result: {result}")
                return result
            else:
                return {"success": False, "message": "No port configured"}
        elif action.action == "stop":
            network_manager.stop_ngrok()
            return {"success": True, "message": "ngrok stopped"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in control_ngrok: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cloudflare")
def control_cloudflare(action: TunnelAction, db: Session = Depends(get_db)):
    """Start or stop cloudflare tunnel"""
    logger.info(f"POST /api/cloudflare called with action: {action.action}")
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        if action.action == "start":
            if config.port:
                result = network_manager.start_cloudflare(config.port)
                logger.info(f"cloudflare result: {result}")
                return result
            else:
                return {"success": False, "message": "No port configured"}
        elif action.action == "stop":
            network_manager.stop_cloudflare()
            return {"success": True, "message": "cloudflare stopped"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in control_cloudflare: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== QUEUE MANAGEMENT ENDPOINTS =====

@app.post("/api/queue/join")
async def join_queue(action: QueueAction, request: Request, db: Session = Depends(get_db)):
    """Join the waiting room queue"""
    logger.debug(f"POST /api/queue/join called with session_id: {action.session_id}")
    try:
        config = db.query(ProjectConfig).first()
        
        # If queue is disabled or request is local, grant immediate access
        if not config or not config.queue_enabled or is_local_request(request):
            session_id = action.session_id or str(uuid.uuid4())
            logger.info(f"Queue bypassed for session {session_id}")
            return {
                "session_id": session_id,
                "status": "active",
                "position": 0,
                "message": "Access granted (queue bypassed)"
            }
        
        result = queue_manager.join_queue(action.session_id)
        logger.info(f"Queue join result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in join_queue: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/queue/leave")
async def leave_queue(action: QueueAction):
    """Leave the queue"""
    logger.debug(f"POST /api/queue/leave called with session_id: {action.session_id}")
    try:
        if not action.session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        
        result = queue_manager.leave_queue(action.session_id)
        logger.info(f"Queue leave result: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in leave_queue: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/queue/heartbeat")
async def queue_heartbeat(action: QueueAction):
    """Send heartbeat to maintain queue position"""
    logger.debug(f"POST /api/queue/heartbeat called with session_id: {action.session_id}")
    try:
        if not action.session_id:
            raise HTTPException(status_code=400, detail="session_id required")
        
        result = queue_manager.heartbeat(action.session_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in queue_heartbeat: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/queue/status")
def get_queue_status():
    """Get current queue state (admin view)"""
    logger.debug("GET /api/queue/status called")
    try:
        state = queue_manager.get_queue_state()
        logger.debug(f"Queue state: {state}")
        return state
    except Exception as e:
        logger.error(f"Error in get_queue_status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/queue/my-status/{session_id}")
def get_my_queue_status(session_id: str):
    """Get status for a specific session"""
    logger.debug(f"GET /api/queue/my-status/{session_id} called")
    try:
        status = queue_manager.get_user_status(session_id)
        if not status:
            raise HTTPException(status_code=404, detail="Session not found")
        logger.debug(f"User status: {status}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_my_queue_status: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== WEBSOCKET ENDPOINTS =====

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket for real-time server logs"""
    logger.info("WebSocket /ws/logs connection attempt")
    
    # Enforce connection limit
    if len(log_connections) >= MAX_WS_CONNECTIONS:
        logger.warning(f"WebSocket connection rejected: limit reached ({MAX_WS_CONNECTIONS})")
        await websocket.close(code=1013, reason="Too many connections")
        return
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket /ws/logs connection accepted ({len(log_connections)+1}/{MAX_WS_CONNECTIONS})")
        log_connections.append(websocket)
        
        try:
            while True:
                # Keep connection alive
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("WebSocket /ws/logs disconnected")
            if websocket in log_connections:
                log_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket /ws/logs error: {e}")
        logger.error(traceback.format_exc())
        if websocket in log_connections:
            log_connections.remove(websocket)


@app.websocket("/ws/queue")
async def websocket_queue(websocket: WebSocket):
    """WebSocket for real-time queue updates"""
    logger.info("WebSocket /ws/queue connection attempt")
    try:
        await websocket.accept()
        logger.info("WebSocket /ws/queue connection accepted")
        queue_connections.append(websocket)
        
        # Add callback to queue manager
        async def send_update(state):
            try:
                await websocket.send_json(state)
            except Exception as e:
                logger.error(f"Error sending queue update: {e}")
        
        queue_manager.add_callback(send_update)
        
        try:
            # Send initial state
            await websocket.send_json(queue_manager.get_queue_state())
            
            while True:
                # Keep connection alive
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("WebSocket /ws/queue disconnected")
            queue_connections.remove(websocket)
            queue_manager.remove_callback(send_update)
    except Exception as e:
        logger.error(f"WebSocket /ws/queue error: {e}")
        logger.error(traceback.format_exc())


# ===== TRAFFIC MONITORING ENDPOINTS =====

@app.get("/api/traffic/metrics")
def get_traffic_metrics():
    """Get aggregated traffic metrics"""
    try:
        active_connections = len(log_connections) + len(queue_connections) + len(traffic_connections)
        return traffic_monitor.get_metrics(active_connections)
    except Exception as e:
        logger.error(f"Error in get_traffic_metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/traffic/requests")
def get_traffic_requests(count: int = 50):
    """Get recent request history"""
    try:
        count = min(count, 200)  # Cap at 200
        return {"requests": traffic_monitor.get_recent_requests(count)}
    except Exception as e:
        logger.error(f"Error in get_traffic_requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/traffic/endpoints")
def get_endpoint_stats():
    """Get per-endpoint statistics"""
    try:
        return {"endpoints": traffic_monitor.get_endpoint_stats()}
    except Exception as e:
        logger.error(f"Error in get_endpoint_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/traffic/connections")
def get_active_connections():
    """Get list of active WebSocket connections"""
    try:
        connections = []
        for i, ws in enumerate(log_connections):
            connections.append({"id": i, "type": "logs", "client": str(ws.client) if ws.client else "unknown"})
        for i, ws in enumerate(queue_connections):
            connections.append({"id": i, "type": "queue", "client": str(ws.client) if ws.client else "unknown"})
        for i, ws in enumerate(traffic_connections):
            connections.append({"id": i, "type": "traffic", "client": str(ws.client) if ws.client else "unknown"})
        return {"connections": connections, "count": len(connections)}
    except Exception as e:
        logger.error(f"Error in get_active_connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/traffic/clear")
def clear_traffic_data():
    """Clear all traffic monitoring data"""
    try:
        traffic_monitor.clear()
        return {"success": True, "message": "Traffic data cleared"}
    except Exception as e:
        logger.error(f"Error in clear_traffic_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/traffic")
async def websocket_traffic(websocket: WebSocket):
    """WebSocket for real-time traffic updates"""
    logger.info("WebSocket /ws/traffic connection attempt")
    
    if len(traffic_connections) >= MAX_WS_CONNECTIONS:
        logger.warning("WebSocket connection rejected: limit reached")
        await websocket.close(code=1013, reason="Too many connections")
        return
    
    try:
        await websocket.accept()
        logger.info(f"WebSocket /ws/traffic connection accepted")
        traffic_connections.append(websocket)
        
        # Callback for real-time updates  
        async def send_traffic_update(data):
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending traffic update: {e}")
        
        # Wrap async callback for sync caller
        def traffic_callback(data):
            if main_loop and main_loop.is_running():
                asyncio.run_coroutine_threadsafe(send_traffic_update(data), main_loop)
        
        traffic_monitor.add_callback(traffic_callback)
        
        try:
            while True:
                # Keep connection alive, also handle ping/pong
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("WebSocket /ws/traffic disconnected")
        finally:
            if websocket in traffic_connections:
                traffic_connections.remove(websocket)
            traffic_monitor.remove_callback(traffic_callback)
    except Exception as e:
        logger.error(f"WebSocket /ws/traffic error: {e}")
        if websocket in traffic_connections:
            traffic_connections.remove(websocket)


# ===== HELPER FUNCTIONS =====

def broadcast_log(log_entry: str):
    """Broadcast log entry to all connected WebSocket clients"""
    # This function is called from a background thread, so we must use run_coroutine_threadsafe
    
    # Only try to broadcast if we have a loop and connections
    if not main_loop or not main_loop.is_running():
        return
        
    if not log_connections:
        return

    # logger.debug(f"Broadcasting log to {len(log_connections)} connections")
    
    # Iterate over a copy to allow safe removal during iteration
    for connection in list(log_connections):
        try:
            # Schedule the coroutine to run on the main event loop
            asyncio.run_coroutine_threadsafe(connection.send_text(log_entry), main_loop)
        except Exception as e:
            logger.error(f"Error broadcasting log: {e}")
            try:
                log_connections.remove(connection)
            except ValueError:
                pass  # Already removed


# ===== BACKGROUND TASKS =====

# queue_timeout_checker is called from lifespan
async def queue_timeout_checker():
    """Periodically check for timed out queue users"""
    logger.debug("Queue timeout checker started")
    while True:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            queue_manager.check_timeouts()
        except asyncio.CancelledError:
            logger.debug("Queue timeout checker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in queue_timeout_checker: {e}")
            logger.error(traceback.format_exc())


# ===== ROOT ENDPOINT =====

@app.get("/")
async def root(request: Request):
    """
    Root endpoint.
    - If Host is a tunnel (ngrok/cloudflare/lan), PROXY to target app.
    - If Host is localhost (127.0.0.1/localhost), SERVE BACKENDBUDDY DASHBOARD.
    """
    host = request.headers.get("host", "").split(":")[0]
    
    # Check if this is a tunnel or LAN access (anything NOT localhost)
    is_tunnel_or_lan = host not in ["127.0.0.1", "localhost", "::1"]
    
    if is_tunnel_or_lan:
        logger.info(f"Tunnel/LAN access detected on host {host} - Proxying to target app")
        return await proxy_to_target(request, path="")
        
    # Localhost access gets the status JSON (API) or Frontend (if mounted)
    logger.debug("Localhost access - Serving BackendBuddy API/Dashboard")
    
    # Check if browser request
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        # If we had the dashboard mounted at root, we'd serve it here.
        # Since we just return JSON for API status currently:
        return {"message": "BackendBuddy API", "status": "running", "dashboard": "http://localhost:1337"}
    
    return {"message": "BackendBuddy API", "status": "running"}


# ===== QUEUE STATUS ENDPOINT =====

@app.get("/api/queue/status/{session_id}")
def get_queue_status(session_id: str):
    """Get queue status for a specific session"""
    status = queue_manager.get_user_status(session_id)
    if status:
        return status
    raise HTTPException(status_code=404, detail="Session not found")


# ===== REVERSE PROXY ENDPOINT =====

import requests
import os as os_module

# Get the directory where main.py is located
STATIC_DIR = os_module.path.join(os_module.path.dirname(__file__), "static")

# Proxy routes - catch the main preview path AND common static asset paths
@app.api_route("/preview/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@app.api_route("/preview", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@app.api_route("/assets/{path:path}", methods=["GET"])
@app.api_route("/static/{path:path}", methods=["GET"])
@app.api_route("/favicon.ico", methods=["GET"])
@app.api_route("/manifest.json", methods=["GET"])
@app.api_route("/robots.txt", methods=["GET"])
@app.api_route("/sitemap.xml", methods=["GET"])
async def proxy_to_target(request: Request, path: str = ""):
    """
    Reverse proxy to the target application.
    Enforces waiting room queue before allowing access.
    """
    # Get config from database
    db = next(get_db())
    try:
        config = db.query(ProjectConfig).first()
        if not config:
            return JSONResponse(status_code=503, content={"error": "No project configured"})
        
        target_port = config.port
        queue_enabled = config.queue_enabled
        max_concurrent = config.max_concurrent_users or 1
        prioritize_localhost = config.prioritize_localhost if config.prioritize_localhost is not None else True
        
        # Configure queue manager with latest settings
        queue_manager.configure(max_concurrent=max_concurrent, prioritize_localhost=prioritize_localhost)
    finally:
        db.close()
    
    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    
    # For tunnel traffic, check X-Forwarded-For header for real client IP
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # Use the first IP in the chain (original client)
        real_ip = forwarded_for.split(",")[0].strip()
        is_localhost = real_ip in ("127.0.0.1", "localhost", "::1")
        logger.debug(f"Proxy request from {client_ip}, X-Forwarded-For: {forwarded_for}, real_ip: {real_ip}, is_localhost: {is_localhost}")
    else:
        is_localhost = client_ip in ("127.0.0.1", "localhost", "::1")
        logger.debug(f"Proxy request from {client_ip}, is_localhost: {is_localhost}")
    
    # Get or create session ID from cookie
    session_id = request.cookies.get("bb_session_id")
    new_session = False
    if not session_id:
        session_id = str(uuid.uuid4())
        new_session = True
        logger.debug(f"New session created: {session_id}")
    else:
        logger.debug(f"Existing session: {session_id}")
    
    # Check queue if enabled
    if queue_enabled:
        # Join or check queue status
        queue_result = queue_manager.join_queue(session_id=session_id, is_localhost=is_localhost)
        logger.info(f"Queue result for {session_id}: {queue_result['status']}")
        
        if queue_result["status"] != "active":
            # User is waiting - serve waiting room
            waiting_room_path = os_module.path.join(STATIC_DIR, "waiting_room.html")
            try:
                with open(waiting_room_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                
                # Inject session ID into the HTML so JavaScript can access it
                # Replace a placeholder or inject before </head>
                injection_script = f'<script>window.BB_SESSION_ID = "{session_id}";</script>'
                html_content = html_content.replace('</head>', f'{injection_script}</head>')
                
                response = HTMLResponse(content=html_content, status_code=200)
                # Set session cookie (httponly for security, JS uses injected var)
                response.set_cookie(
                    key="bb_session_id",
                    value=session_id,
                    httponly=True,
                    samesite="lax",
                    max_age=3600  # 1 hour
                )
                return response
            except FileNotFoundError:
                return JSONResponse(
                    status_code=503, 
                    content={
                        "error": "Waiting room not available",
                        "queue_status": queue_result
                    }
                )
        
        # User is active - update heartbeat
        queue_manager.heartbeat(session_id)
    
    # Forward request to target application
    # Use 127.0.0.1 instead of localhost to avoid IPv6 resolution issues
    # Use request.url.path to get the full path (handles /assets, /static, etc.)
    request_path = request.url.path
    # Strip /preview prefix if present (but keep /assets, /static, etc.)
    if request_path.startswith("/preview"):
        request_path = request_path[8:]  # Remove "/preview"
        if not request_path:
            request_path = "/"
    
    target_url = f"http://127.0.0.1:{target_port}{request_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"
    
    logger.info(f"Proxying to target: {target_url}")
    
    try:
        # Get request body
        body = await request.body()
        
        # Forward headers (excluding host)
        forward_headers = {}
        for key, value in request.headers.items():
            if key.lower() not in ('host', 'content-length'):
                forward_headers[key] = value
        
        # Make request to target
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            data=body,
            allow_redirects=False,
            timeout=30
        )
        
        # Build response headers
        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        response_headers = {}
        for key, value in resp.headers.items():
            if key.lower() not in excluded_headers:
                response_headers[key] = value
        
        logger.info(f"Target responded: status={resp.status_code}, content_type={resp.headers.get('content-type')}, size={len(resp.content)} bytes")
        
        # Create response
        response = Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
            media_type=resp.headers.get('content-type')
        )
        
        # Set session cookie if new
        if new_session:
            response.set_cookie(
                key="bb_session_id",
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=3600
            )
        
        return response
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to target: {target_url}")
        return JSONResponse(
            status_code=502, 
            content={"error": "Target application not responding", "target": target_url}
        )
    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=504,
            content={"error": "Target application timeout"}
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=502, 
            content={"error": "Bad Gateway", "details": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    import os
    logger.info("=" * 50)
    logger.info("STARTING BACKENDBUDDY SERVER")
    logger.info("=" * 50)
    
    use_https = os.environ.get("USE_HTTPS", "false").lower() == "true"
    
    ssl_keyfile = None
    ssl_certfile = None
    
    if use_https:
        logger.info("HTTPS MODE ENABLED")
        try:
            from cert_utils import get_ssl_context
            cert, key = get_ssl_context()
            if cert and key:
                ssl_certfile = cert
                ssl_keyfile = key
                logger.info(f"Using cert: {cert}, key: {key}")
            else:
                logger.error("Failed to generate/load certificates. Falling back to HTTP.")
        except Exception as e:
            logger.error(f"Error initializing HTTPS: {e}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=1338, 
        log_level="debug",
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile
    )
