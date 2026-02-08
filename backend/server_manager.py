import subprocess
import psutil
import threading
import queue
import os
import logging
import traceback
from typing import Optional, Callable
from datetime import datetime
from collections import deque

# Set up logging
logger = logging.getLogger("BackendBuddy.ServerManager")


class ServerManager:
    """Manages the lifecycle of a single dev server process"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.log_queue = deque(maxlen=1000)
        self.log_callbacks = []
        self.is_running = False
        logger.debug("ServerManager initialized")
        
    def start(self, directory: str, command: str, frontend_directory: Optional[str] = None, frontend_command: Optional[str] = None, log_callback: Optional[Callable] = None):
        """Start the dev server(s)"""
        logger.info(f"Starting server: dir={directory}, cmd={command}, frontend_dir={frontend_directory}, frontend_cmd={frontend_command}")
        
        if self.is_running:
            logger.warning("Server is already running, cannot start another")
            return {"success": False, "message": "Server is already running"}
        
        try:
            # Validate directory
            if not os.path.exists(directory):
                logger.error(f"Directory does not exist: {directory}")
                return {"success": False, "message": f"Directory does not exist: {directory}"}
            
            if not os.path.isdir(directory):
                logger.error(f"Path is not a directory: {directory}")
                return {"success": False, "message": f"Path is not a directory: {directory}"}
            
            # Basic command sanitization - block obvious shell injection attempts
            dangerous_patterns = ['$(', '`', '|', '>', '<', ';', '\n', '\r']
            for pattern in dangerous_patterns:
                if pattern in command:
                    logger.error(f"Dangerous pattern detected in command: {pattern}")
                    return {"success": False, "message": f"Invalid command: contains forbidden character"}
            
            logger.debug(f"Directory exists: {directory}")
            logger.debug(f"Starting process with command: {command}")
            
            # Clear previous callbacks to prevent accumulation
            self.log_callbacks = []
            
            # Start process
            try:
                # Set UTF-8 encoding for Python subprocesses to avoid Windows encoding issues
                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                env['PYTHONUNBUFFERED'] = '1'
                
                self.process = subprocess.Popen(
                    command,
                    cwd=directory,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                    encoding='utf-8',
                    errors='replace'
                )
                
                logger.info(f"Process started with PID: {self.process.pid}")
                self.is_running = True
                
                # Start log streaming thread
                if log_callback:
                    self.log_callbacks.append(log_callback)
                    logger.debug(f"Added log callback, total callbacks: {len(self.log_callbacks)}")
                
                log_thread = threading.Thread(target=self._stream_logs, args=(self.process, "[Backend] "), daemon=True)
                log_thread.start()
                logger.debug("Backend log streaming thread started")

                # Start Frontend Process if configured
                if frontend_directory and frontend_command:
                    logger.info(f"Starting frontend: dir={frontend_directory}, cmd={frontend_command}")
                    frontend_path = frontend_directory
                    if not os.path.isabs(frontend_path):
                        # If relative, assume relative to backend directory parent? Or just project root?
                        # Let's assume absolute or relative to where CWD is? 
                        # Actually commonly relative to project root. 
                        # But wait, 'directory' (backend) might be ./backend.
                        # For safety, let's assume raw string first.
                        pass

                    if os.path.exists(frontend_path):
                         self.frontend_process = subprocess.Popen(
                            frontend_command,
                            cwd=frontend_path,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            env=env,
                            encoding='utf-8',
                            errors='replace'
                        )
                         logger.info(f"Frontend started with PID: {self.frontend_process.pid}")
                         fe_log_thread = threading.Thread(target=self._stream_logs, args=(self.frontend_process, "[Frontend] "), daemon=True)
                         fe_log_thread.start()
                    else:
                        logger.warning(f"Frontend directory not found: {frontend_path}")
                        self.log_queue.append(f"[System] [WARNING] Frontend directory not found: {frontend_path}")
                
                return {
                    "success": True,
                    "message": "Server(s) started successfully",
                    "pid": self.process.pid,
                    "frontend_pid": self.frontend_process.pid if self.frontend_process else None
                }
            except Exception as e:
                # Emergency cleanup if startup fails halfway
                logger.error(f"Critical error during startup: {e}")
                if self.process:
                    try:
                        self.process.kill()
                    except:
                        pass
                self.process = None
                self.is_running = False
                raise e
            
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            self.is_running = False
            return {"success": False, "message": f"Command not found: {str(e)}"}
        except PermissionError as e:
            logger.error(f"Permission denied: {e}")
            self.is_running = False
            return {"success": False, "message": f"Permission denied: {str(e)}"}
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            logger.error(traceback.format_exc())
            self.is_running = False
            return {"success": False, "message": f"Failed to start server: {str(e)}"}
    
    def _stream_logs(self, process: subprocess.Popen, prefix: str = ""):
        """Stream logs from a specific process"""
        logger.debug(f"Log streaming started for {prefix}")
        
        if not process or not process.stdout:
            logger.error(f"No process or stdout to stream from for {prefix}")
            return
        
        try:
            line_count = 0
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                line_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_entry = f"[{timestamp}] {prefix}{line.rstrip()}"
                
                # Log every 10th line to avoid spam
                if line_count <= 5 or line_count % 10 == 0:
                    logger.debug(f"Log line {line_count}: {log_entry[:100]}...")
                
                # Send to all callbacks
                for callback in self.log_callbacks:
                    try:
                        callback(log_entry)
                    except Exception as e:
                        logger.error(f"Log callback error: {e}")
                
                # Also store in queue for retrieval (deque handles maxlen automatically)
                self.log_queue.append(log_entry)
            
            logger.info(f"Log streaming ended after {line_count} lines")
                
        except Exception as e:
            logger.error(f"Log streaming failed: {e}")
            logger.error(traceback.format_exc())
            error_msg = f"[ERROR] Log streaming failed: {str(e)}"
            for callback in self.log_callbacks:
                try:
                    callback(error_msg)
                except Exception as cb_error:
                    logger.error(f"Error callback failed: {cb_error}")
        finally:
            logger.debug("Log streaming thread exiting, setting is_running=False")
            self.is_running = False
    
    def stop(self):
        """Stop the dev server gracefully"""
        logger.info("Stopping server")
        
        if not self.process or not self.is_running:
            logger.warning("No server is running")
            return {"success": False, "message": "No server is running"}
        
        try:
            pid = self.process.pid
            logger.debug(f"Stopping process with PID: {pid}")
            
            parent = psutil.Process(pid)
            
            # Kill all child processes
            children = parent.children(recursive=True)
            logger.debug(f"Found {len(children)} child processes")
            
            for child in children:
                try:
                    logger.debug(f"Terminating child PID: {child.pid}")
                    child.terminate()
                except psutil.NoSuchProcess:
                    logger.debug(f"Child process {child.pid} already gone")
                except Exception as e:
                    logger.error(f"Error terminating child {child.pid}: {e}")
            
            # Kill parent
            logger.debug(f"Terminating parent PID: {pid}")
            parent.terminate()
            
            # Wait for termination
            try:
                parent.wait(timeout=5)
                logger.info(f"Process {pid} terminated gracefully")
            except psutil.TimeoutExpired:
                logger.warning(f"Process {pid} did not terminate in time, killing")
                parent.kill()
                for child in children:
                    try:
                        child.kill()
                    except Exception as e:
                        logger.debug(f"Error killing child: {e}")
            
            # Stop Frontend if running
            if self.frontend_process:
                try:
                    fe_pid = self.frontend_process.pid
                    logger.debug(f"Stopping frontend PID: {fe_pid}")
                    fe_parent = psutil.Process(fe_pid)
                    for child in fe_parent.children(recursive=True):
                        child.terminate()
                    fe_parent.terminate()
                    self.frontend_process = None
                except Exception as e:
                    logger.error(f"Error stopping frontend: {e}")

            self.is_running = False
            self.process = None
            
            return {"success": True, "message": "Server stopped successfully"}
            
        except psutil.NoSuchProcess:
            logger.warning("Process already terminated")
            self.is_running = False
            self.process = None
            return {"success": True, "message": "Server already stopped"}
        except Exception as e:
            logger.error(f"Failed to stop server: {e}")
            logger.error(traceback.format_exc())
            # Force reset state to avoid getting stuck
            self.is_running = False
            self.process = None
            return {"success": False, "message": f"Failed to stop server: {str(e)}"}
    
    def restart(self, directory: str, command: str, frontend_directory: Optional[str] = None, frontend_command: Optional[str] = None):
        """Restart the server"""
        logger.info(f"Restarting server: directory={directory}")
        
        stop_result = self.stop()
        logger.debug(f"Stop result: {stop_result}")
        
        if not stop_result["success"] and self.is_running:
            logger.error("Failed to stop server for restart")
            return stop_result
        
        # Small delay to ensure cleanup
        import time
        logger.debug("Waiting 1 second for cleanup...")
        time.sleep(1)
        
        return self.start(directory, command, frontend_directory, frontend_command)
    
    def get_status(self):
        """Get current server status by checking actual process state"""
        logger.debug("Getting server status")
        
        # If we have a process reference, check if it's actually running
        if self.process:
            try:
                proc = psutil.Process(self.process.pid)
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    uptime = datetime.now().timestamp() - proc.create_time()
                    self.is_running = True  # Sync flag with reality
                    status = {
                        "running": True,
                        "pid": self.process.pid,
                        "uptime": int(uptime)
                    }
                    logger.debug(f"Server status: {status}")
                    return status
            except psutil.NoSuchProcess:
                logger.debug("Process not found")
            except Exception as e:
                logger.debug(f"Error checking process: {e}")
        
        # No process or process not running
        logger.debug("Server is not running")
        self.is_running = False
        return {
            "running": False,
            "pid": None,
            "uptime": None
        }
    
    def get_recent_logs(self, count: int = 50):
        """Get recent log entries"""
        logger.debug(f"Getting recent {count} logs")
        
        # Deque allows direct conversion to list
        # It's thread-safe enough for this purpose (snapshot)
        all_logs = list(self.log_queue)
        
        result = all_logs[-count:] if all_logs else []
        logger.debug(f"Returning {len(result)} log entries")
        return result

    def scan_project(self, root_path: str):
        """
        Scans a directory recursively to auto-detect backend and frontend configurations.
        Returns a dictionary with suggested settings.
        """
        logger.info(f"Scanning project at: {root_path}")
        
        if not os.path.exists(root_path):
            return {"success": False, "message": "Path does not exist"}

        config = {
            "name": os.path.basename(root_path),
            "directory": "",
            "command": "",
            "frontend_directory": "",
            "frontend_command": "",
            "success": True
        }

        # BFS scan to find 'best' candidates first (prefer top-level or immediate subdirs)
        # We limit depth to avoid scanning massive node_modules or venvs deeply
        
        found_backend = False
        found_frontend = False

        try:
            for root, dirs, files in os.walk(root_path):
                # Calculate depth to limit search
                depth = root[len(root_path):].count(os.sep)
                if depth > 2:
                    continue
                
                # skip node_modules, venv, .git
                if 'node_modules' in root or 'venv' in root or '.git' in root or '__pycache__' in root:
                    continue
                
                logger.debug(f"Scanning {root}, files: {files[:10]}...")  # Log first 10 files

                # --- Backend Detection ---
                if not found_backend:
                    # Check for venv in this directory
                    has_venv = os.path.exists(os.path.join(root, 'venv', 'Scripts', 'activate.bat'))
                    venv_prefix = r'.\\venv\\Scripts\\activate && ' if has_venv else ''
                    
                    # Priority 1: launcher.py (Chattermax style)
                    if 'launcher.py' in files:
                        config['directory'] = root
                        config['command'] = f'{venv_prefix}python launcher.py --http'
                        found_backend = True
                        logger.info(f"Found Backend (launcher.py) at {root}, venv={has_venv}")
                    # Priority 2: manage.py (Django)
                    elif 'manage.py' in files:
                        config['directory'] = root
                        config['command'] = f'{venv_prefix}python manage.py runserver 0.0.0.0:8000'
                        found_backend = True
                        logger.info(f"Found Backend (Django) at {root}, venv={has_venv}")
                    # Priority 3: main.py or app.py (Generic)
                    elif 'main.py' in files:
                        config['directory'] = root
                        config['command'] = f'{venv_prefix}python main.py'
                        found_backend = True
                        logger.info(f"Found Backend (main.py) at {root}, venv={has_venv}")
                    elif 'app.py' in files:
                        config['directory'] = root
                        config['command'] = f'{venv_prefix}python app.py'
                        found_backend = True
                        logger.info(f"Found Backend (app.py) at {root}, venv={has_venv}")
                    # Priority 4: server.js (Node.js Backend)
                    elif 'server.js' in files:
                        config['directory'] = root
                        # Use simple command to avoid shell issues. User can add 'npm install' if needed manually.
                        config['command'] = 'node server.js'
                        found_backend = True
                        logger.info(f"Found Backend (server.js) at {root}")

                # --- Frontend Detection ---
                # Skip frontend detection if backend (server.js) is in same directory 
                # to avoid running the same app twice
                if not found_frontend:
                    # Don't detect frontend in same dir as a server.js backend
                    if found_backend and config.get('directory') == root and 'server.js' in files:
                        logger.debug(f"Skipping frontend detection - server.js backend in same directory")
                    elif 'package.json' in files:
                        # Check if it has 'dev' or 'start' script
                        try:
                            import json
                            with open(os.path.join(root, 'package.json'), 'r') as f:
                                pkg = json.load(f)
                                scripts = pkg.get('scripts', {})
                                
                                if 'dev' in scripts:
                                    config['frontend_directory'] = root
                                    config['frontend_command'] = 'npm run dev'
                                    found_frontend = True
                                    logger.info(f"Found Frontend (npm run dev) at {root}")
                                elif 'start' in scripts:
                                    config['frontend_directory'] = root
                                    config['frontend_command'] = 'npm start'
                                    found_frontend = True
                                    logger.info(f"Found Frontend (npm start) at {root}")
                        except Exception as e:
                            logger.warning(f"Failed to read package.json at {root}: {e}")

                if found_backend and found_frontend:
                    break
            
            # If nothing specific found, check for requirements.txt as fallback for backend
            if not found_backend:
                 for root, dirs, files in os.walk(root_path):
                    if 'requirements.txt' in files and 'node_modules' not in root:
                        config['directory'] = root
                        config['command'] = 'python app.py' # generic fallback
                        found_backend = True
                        logger.info(f"Found Backend (requirements.txt match) at {root}")
                        break

            return config

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": str(e)}


# Global server manager instance
server_manager = ServerManager()
logger.info("Global ServerManager instance created")
