"""
Traffic Monitor - Tracks HTTP requests to BackendBuddy API
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import deque
from typing import List, Dict, Optional, Callable
import threading
import time
import logging

logger = logging.getLogger("BackendBuddy.TrafficMonitor")


@dataclass
class RequestLog:
    """Single request record"""
    timestamp: str
    method: str
    path: str
    status: int
    latency_ms: float
    client_ip: str
    user_agent: str
    bytes_in: int
    bytes_out: int
    
    def to_dict(self):
        return asdict(self)


@dataclass
class TrafficMetrics:
    """Aggregated traffic statistics"""
    total_requests: int
    requests_per_second: float
    avg_latency_ms: float
    error_rate: float
    bytes_in_total: int
    bytes_out_total: int
    active_connections: int
    uptime_seconds: int
    
    def to_dict(self):
        return asdict(self)


class TrafficMonitor:
    """In-memory traffic tracking with real-time streaming"""
    
    def __init__(self, max_history: int = 500):
        self.max_history = max_history
        self.request_history: deque = deque(maxlen=max_history)
        self.endpoint_stats: Dict[str, Dict] = {}
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        # Metrics tracking
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.bytes_in_total = 0
        self.bytes_out_total = 0
        self.start_time = time.time()
        
        # For requests/sec calculation
        self.recent_timestamps: deque = deque(maxlen=100)
        
        logger.info("TrafficMonitor initialized")
    
    def log_request(
        self,
        method: str,
        path: str,
        status: int,
        latency_ms: float,
        client_ip: str,
        user_agent: str,
        bytes_in: int = 0,
        bytes_out: int = 0
    ):
        """Log a completed request"""
        now = datetime.now()
        
        log_entry = RequestLog(
            timestamp=now.isoformat(),
            method=method,
            path=path,
            status=status,
            latency_ms=round(latency_ms, 2),
            client_ip=client_ip,
            user_agent=user_agent[:100] if user_agent else "",
            bytes_in=bytes_in,
            bytes_out=bytes_out
        )
        
        with self._lock:
            # Add to history
            self.request_history.append(log_entry)
            
            # Update totals
            self.total_requests += 1
            self.total_latency_ms += latency_ms
            self.bytes_in_total += bytes_in
            self.bytes_out_total += bytes_out
            
            if status >= 400:
                self.total_errors += 1
            
            # Track for requests/sec
            self.recent_timestamps.append(now.timestamp())
            
            # Update endpoint stats
            endpoint_key = f"{method} {path.split('?')[0]}"
            if endpoint_key not in self.endpoint_stats:
                self.endpoint_stats[endpoint_key] = {
                    "count": 0,
                    "errors": 0,
                    "total_latency": 0.0,
                    "method": method,
                    "path": path.split('?')[0]
                }
            
            stats = self.endpoint_stats[endpoint_key]
            stats["count"] += 1
            stats["total_latency"] += latency_ms
            if status >= 400:
                stats["errors"] += 1
        
        # Notify callbacks (for WebSocket streaming)
        for callback in self.callbacks:
            try:
                callback(log_entry.to_dict())
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_recent_requests(self, count: int = 50) -> List[Dict]:
        """Get recent request history"""
        with self._lock:
            items = list(self.request_history)[-count:]
            return [r.to_dict() for r in reversed(items)]
    
    def get_metrics(self, active_connections: int = 0) -> Dict:
        """Get aggregated traffic metrics"""
        with self._lock:
            # Calculate requests per second
            now = time.time()
            recent = [t for t in self.recent_timestamps if now - t < 60]
            rps = len(recent) / 60.0 if recent else 0.0
            
            # Calculate averages
            avg_latency = (
                self.total_latency_ms / self.total_requests 
                if self.total_requests > 0 else 0.0
            )
            error_rate = (
                (self.total_errors / self.total_requests) * 100 
                if self.total_requests > 0 else 0.0
            )
            
            return TrafficMetrics(
                total_requests=self.total_requests,
                requests_per_second=round(rps, 2),
                avg_latency_ms=round(avg_latency, 2),
                error_rate=round(error_rate, 2),
                bytes_in_total=self.bytes_in_total,
                bytes_out_total=self.bytes_out_total,
                active_connections=active_connections,
                uptime_seconds=int(now - self.start_time)
            ).to_dict()
    
    def get_endpoint_stats(self) -> List[Dict]:
        """Get per-endpoint breakdown"""
        with self._lock:
            result = []
            for key, stats in self.endpoint_stats.items():
                avg_latency = (
                    stats["total_latency"] / stats["count"] 
                    if stats["count"] > 0 else 0.0
                )
                result.append({
                    "endpoint": key,
                    "method": stats["method"],
                    "path": stats["path"],
                    "count": stats["count"],
                    "errors": stats["errors"],
                    "avg_latency_ms": round(avg_latency, 2),
                    "error_rate": round(
                        (stats["errors"] / stats["count"]) * 100 
                        if stats["count"] > 0 else 0.0, 
                        2
                    )
                })
            
            # Sort by count descending
            result.sort(key=lambda x: x["count"], reverse=True)
            return result
    
    def add_callback(self, callback: Callable):
        """Add real-time update callback"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def clear(self):
        """Clear all data"""
        with self._lock:
            self.request_history.clear()
            self.endpoint_stats.clear()
            self.total_requests = 0
            self.total_errors = 0
            self.total_latency_ms = 0.0
            self.bytes_in_total = 0
            self.bytes_out_total = 0
            self.recent_timestamps.clear()
            self.start_time = time.time()
        logger.info("TrafficMonitor cleared")


# Global instance
traffic_monitor = TrafficMonitor()
