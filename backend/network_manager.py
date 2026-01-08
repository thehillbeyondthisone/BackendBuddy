import subprocess
import platform
import shutil
import re
import time
import logging
import traceback
import socket
import requests
from typing import Optional, Dict, List

# Set up logging
logger = logging.getLogger("BackendBuddy.NetworkManager")

from database import get_db, ProjectConfig



class NetworkManager:
    """Manages network links and ngrok tunnels"""
    
    def __init__(self):
        self.ngrok_process: Optional[subprocess.Popen] = None
        self.ngrok_url: Optional[str] = None
        self.cloudflare_process: Optional[subprocess.Popen] = None
        self.cloudflare_url: Optional[str] = None
        logger.debug("NetworkManager initialized")
    
    def get_lan_ips(self) -> List[str]:
        """Auto-detect all LAN IP addresses for this machine"""
        logger.debug("Auto-detecting LAN IP addresses")
        ips = []
        try:
            # Get hostname
            hostname = socket.gethostname()
            logger.debug(f"Hostname: {hostname}")
            
            # Get all IP addresses associated with hostname
            try:
                host_ips = socket.gethostbyname_ex(hostname)[2]
                for ip in host_ips:
                    if not ip.startswith("127."):
                        ips.append(ip)
                        logger.debug(f"Found IP from hostname: {ip}")
            except Exception as e:
                logger.debug(f"gethostbyname_ex failed: {e}")
            
            # Also try connecting to external address to find default route IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                default_ip = s.getsockname()[0]
                s.close()
                if default_ip not in ips and not default_ip.startswith("127."):
                    ips.append(default_ip)
                    logger.debug(f"Found default route IP: {default_ip}")
            except Exception as e:
                logger.debug(f"Default route detection failed: {e}")
            
            logger.info(f"Detected LAN IPs: {ips}")
            return ips
        except Exception as e:
            logger.error(f"Failed to detect LAN IPs: {e}")
            logger.error(traceback.format_exc())
            return []
        
    def generate_links(self, port: int, lan_ip: str, ngrok_enabled: bool) -> Dict:
        """Generate all access links"""
        logger.debug(f"Generating links: port={port}, lan_ip={lan_ip}, ngrok_enabled={ngrok_enabled}")
        
        links = {
            "localhost": f"http://localhost:{port}",
            "lan": None,
            "ngrok": None
        }
        
        # Add LAN link if IP is configured
        if lan_ip and lan_ip.strip():
            links["lan"] = f"http://{lan_ip}:{port}"
            logger.debug(f"LAN link: {links['lan']}")
        
        # Add ngrok link if enabled
        if ngrok_enabled and self.ngrok_url:
            links["ngrok"] = self.ngrok_url
            logger.debug(f"ngrok link: {links['ngrok']}")
        
        return links
    
    def start_ngrok(self, port: int) -> Dict:
        """Start ngrok tunnel"""
        logger.info(f"Starting ngrok on port {port}")
        
        if self.ngrok_process:
            if self.ngrok_process.poll() is None and self.ngrok_url:
                logger.info(f"ngrok already running at {self.ngrok_url}")
                return {
                    "success": True, 
                    "url": self.ngrok_url, 
                    "message": "ngrok already running"
                }
            else:
                # Process is dead but object exists, clean up
                self.ngrok_process = None
                self.ngrok_url = None
        
        try:
            # Determine port based on configuration
            target_port = port  # Default to requested port
            
            # Check if queue is enabled via DB
            try:
                db = next(get_db())
                config = db.query(ProjectConfig).first()
                if config and config.queue_enabled:
                    target_port = 1338  # Use proxy port
                    logger.info("Queue enabled: Tunneling Traffic through BackendBuddy Proxy (1338)")
                else:
                    logger.info(f"Queue disabled: Tunneling directly to target port ({port})")
                db.close()
            except Exception as e:
                logger.error(f"Error checking DB for queue config: {e}")
                
            logger.debug(f"Executing: ngrok http {target_port}")
            self.ngrok_process = subprocess.Popen(
                ["ngrok", "http", str(target_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.debug(f"ngrok process started with PID: {self.ngrok_process.pid}")
            
            # Wait for ngrok to start and get URL
            logger.debug("Waiting 2 seconds for ngrok to start...")
            time.sleep(2)
            
            # Query ngrok API for tunnel URL
            logger.debug("Querying ngrok API at http://localhost:4040/api/tunnels")
            try:
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                logger.debug(f"ngrok API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"ngrok API response: {data}")
                    tunnels = data.get("tunnels", [])
                    if tunnels:
                        self.ngrok_url = tunnels[0].get("public_url", "")
                        logger.info(f"ngrok tunnel established: {self.ngrok_url}")
                        return {
                            "success": True,
                            "url": self.ngrok_url,
                            "message": "ngrok started successfully"
                        }
                    else:
                        logger.warning("No tunnels found in ngrok API response")
                else:
                    logger.warning(f"ngrok API returned status {response.status_code}")
            except requests.RequestException as e:
                logger.error(f"Failed to query ngrok API: {e}")
            
            return {
                "success": False,
                "message": "Failed to retrieve ngrok URL. Is ngrok running?"
            }
            
        except FileNotFoundError:
            logger.error("ngrok executable not found")
            return {
                "success": False,
                "message": "ngrok not found. Please ensure it's installed globally."
            }
        except Exception as e:
            logger.error(f"Failed to start ngrok: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"Failed to start ngrok: {str(e)}"}
    
    def stop_ngrok(self) -> Dict:
        """Stop ngrok tunnel"""
        logger.info("Stopping ngrok")
        
        if not self.ngrok_process:
            logger.debug("ngrok is not running")
            return {"success": False, "message": "ngrok is not running"}
        
        try:
            logger.debug(f"Terminating ngrok process PID: {self.ngrok_process.pid}")
            self.ngrok_process.terminate()
            self.ngrok_process.wait(timeout=5)
            self.ngrok_process = None
            self.ngrok_url = None
            logger.info("ngrok stopped successfully")
            return {"success": True, "message": "ngrok stopped successfully"}
        except subprocess.TimeoutExpired:
            logger.warning("ngrok did not terminate in time, killing")
            try:
                self.ngrok_process.kill()
                self.ngrok_process = None
                self.ngrok_url = None
            except Exception as e:
                logger.error(f"Failed to kill ngrok: {e}")
            return {"success": True, "message": "ngrok killed"}
        except Exception as e:
            logger.error(f"Failed to stop ngrok: {e}")
            logger.error(traceback.format_exc())

    def start_cloudflare(self, port: int):
        """Start cloudflared tunnel"""
        logger.info(f"Starting cloudflared on port {port}")
        
        if self.cloudflare_process:
            if self.cloudflare_process.poll() is None and self.cloudflare_url:
                 logger.info(f"cloudflared already running at {self.cloudflare_url}")
                 return {
                     "success": True, 
                     "url": self.cloudflare_url, 
                     "message": "cloudflared already running"
                 }
            else:
                self.stop_cloudflare()
            
        try:
            # Check if cloudflared is installed
            if not shutil.which("cloudflared"):
                return {"success": False, "message": "cloudflared not found in PATH"}

            # Determine port based on configuration
            target_port = port  # Default to requested port
            
            # Check if queue is enabled via DB
            try:
                db = next(get_db())
                config = db.query(ProjectConfig).first()
                if config and config.queue_enabled:
                    target_port = 1338  # Use proxy port
                    logger.info("Queue enabled: Tunneling Traffic through BackendBuddy Proxy (1338)")
                else:
                    logger.info(f"Queue disabled: Tunneling directly to target port ({port})")
                db.close()
            except Exception as e:
                logger.error(f"Error checking DB for queue config: {e}")

            # Start process
            cmd = f"cloudflared tunnel --url http://127.0.0.1:{target_port}"
            self.cloudflare_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Find URL in output
            url_found = False
            start_time = time.time()
            
            # We need to read lines without blocking forever
            import threading
            
            def scan_logs():
                nonlocal url_found
                try:
                    for line in iter(self.cloudflare_process.stdout.readline, ''):
                        if not line: break

                        
                        # Look for trycloudflare.com URL
                        # Example: https://random-name.trycloudflare.com
                        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                        if match:
                            self.cloudflare_url = match.group(0)
                            logger.info(f"Cloudflare URL found: {self.cloudflare_url}")
                            url_found = True
                            # Keep reading to prevent buffer fill, but we found what we needed
                except Exception as e:
                    logger.error(f"Error scanning cloudflare logs: {e}")

            t = threading.Thread(target=scan_logs, daemon=True)
            t.start()
            
            # Wait for URL up to 10 seconds
            while not url_found and time.time() - start_time < 10:
                time.sleep(0.5)
                
            if self.cloudflare_url:
                return {"success": True, "message": f"Cloudflare tunnel started: {self.cloudflare_url}", "url": self.cloudflare_url}
            else:
                return {"success": False, "message": "Cloudflare started but URL not found (check logs)"}

        except Exception as e:
            logger.error(f"Failed to start cloudflared: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": str(e)}

    def stop_cloudflare(self):
        """Stop cloudflared tunnel"""
        if not self.cloudflare_process:
            return
            
        try:
            logger.info("Stopping cloudflared...")
            self.cloudflare_process.terminate()
            try:
                self.cloudflare_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.cloudflare_process.kill()
            
            self.cloudflare_process = None
            self.cloudflare_url = None
            logger.info("cloudflared stopped")
        except Exception as e:
            logger.error(f"Failed to stop cloudflared: {e}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"Failed to stop ngrok: {str(e)}"}
    
    def get_ngrok_status(self) -> Dict:
        """Get ngrok status"""
        if not self.ngrok_process:
            return {"running": False, "url": None}
        
        # Check if process is still alive
        if self.ngrok_process.poll() is not None:
            logger.debug("ngrok process has exited")
            self.ngrok_process = None
            self.ngrok_url = None
            return {"running": False, "url": None}
        
        return {"running": True, "url": self.ngrok_url}


# Global network manager instance
network_manager = NetworkManager()
logger.info("Global NetworkManager instance created")
