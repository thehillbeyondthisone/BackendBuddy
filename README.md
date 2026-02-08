# Vibecoding Project Manager

A brutalist-styled tool to manage, deploy, and share development servers for your vibecoding projects. Features automatic server lifecycle management, LAN forwarding, ngrok integration, and a waiting room queue system for remote users (in development).

## Features

- **Single Project Management**: Configure and manage one project at a time with persistent settings
- **Server Control**: Start, stop, and restart your dev server with one click
- **Manual Network Configuration**: Full control over IP and port settings
- **LAN Forwarding**: Share your project across your local network
- **ngrok Integration**: Create public tunnels for remote access
- **Waiting Room Queue**: Ensure only one remote user accesses your project at a time
- **Real-time Logs**: Monitor server output in real-time via WebSocket
- **Bold Brutalist Design**: High-contrast UI with chunky borders, neon colors, and terminal fonts

## Prerequisites

- **Python 3.8+** - [Download](https://www.python.org/)
- **Node.js 16+** - [Download](https://nodejs.org/)
- **ngrok** (optional) - [Download](https://ngrok.com/) - Must be installed globally for tunnel features

## Quick Start

1. **Clone or download this repository**

2. **Run the quickstart script**:
   ```bash
   quickstart.bat
   ```

3. **Access the application**:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

The script will automatically:
- Create a Python virtual environment
- Install all backend dependencies
- Install all frontend dependencies
- Start both servers in separate windows

## Configuration

### Project Settings

1. **Project Name**: A friendly name for your project
2. **Project Directory**: Full path to your project folder
3. **Server Command**: Command to start your dev server (e.g., `npm run dev`, `python -m http.server`)
4. **Port**: Port number your server runs on
5. **LAN IP**: Your machine's IP address on the local network (e.g., `192.168.1.100`)

### Features

- **LAN Forwarding**: Enable to generate LAN access links
- **ngrok Tunnel**: Enable to create a public URL via ngrok
- **Waiting Room Queue**: Enable to restrict remote users to one at a time

## Usage

### Starting Your Project

1. Configure your project settings in the left panel
2. Click **SAVE CONFIG**
3. Click **START** in the Server Control panel
4. Your server will start and logs will appear in real-time
5. Access links will be displayed in the bottom panel

### Sharing Your Project

**Local Network (LAN)**:
- Enable "LAN Forwarding"
- Enter your LAN IP address
- Share the LAN link with devices on your network

**Public Access (ngrok)**:
- Enable "ngrok Tunnel"
- The ngrok URL will appear automatically
- Share this link with anyone on the internet

### Waiting Room Queue

When enabled, remote users will:
1. Join a queue when accessing your project
2. See their position and wait time
3. Automatically get access when it's their turn
4. Local/owner access always bypasses the queue

### Restarting After Changes

1. Make changes to your project code
2. Click **RESTART** in the Server Control panel
3. The server will stop, restart, and maintain all settings
4. ngrok tunnel will be re-established if enabled

## Architecture

### Backend (Python + FastAPI)

- **main.py**: FastAPI application with all API endpoints
- **database.py**: SQLite database for configuration and queue management
- **server_manager.py**: Process management for dev servers
- **queue_manager.py**: Waiting room queue system
- **network_manager.py**: Link generation and ngrok control

### Frontend (React + Vite)

- **App.jsx**: Main application with queue logic
- **ProjectConfig.jsx**: Configuration form
- **ServerControl.jsx**: Server control panel with logs
- **LinkDisplay.jsx**: Access links and queue status
- **WaitingRoom.jsx**: Queue waiting interface
- **index.css**: Brutalist design system

## API Endpoints

### Configuration
- `GET /api/config` - Get current configuration
- `PUT /api/config` - Update configuration

### Server Control
- `POST /api/server` - Control server (start/stop/restart)
- `GET /api/server/status` - Get server status
- `GET /api/server/logs` - Get recent logs

### Network
- `GET /api/links` - Get all access links

### Queue Management
- `POST /api/queue/join` - Join the queue
- `POST /api/queue/leave` - Leave the queue
- `POST /api/queue/heartbeat` - Maintain queue position
- `GET /api/queue/status` - Get queue state (admin)
- `GET /api/queue/my-status/{session_id}` - Get user status

### WebSockets
- `WS /ws/logs` - Real-time server logs
- `WS /ws/queue` - Real-time queue updates

## Troubleshooting

### Server won't start
- Check that the project directory exists
- Verify the server command is correct
- Ensure the port is not already in use

### ngrok not working
- Verify ngrok is installed globally: `ngrok version`
- Check that ngrok is in your system PATH
- Ensure port 4040 is not blocked (ngrok API)

### Queue not working
- Verify "Waiting Room Queue" is enabled in settings
- Check that remote users are not accessing from localhost
- Monitor queue status in the Link Display panel

### Links not appearing
- Ensure the server is running
- Check that port and LAN IP are configured correctly
- For ngrok, wait a few seconds after enabling

## Design Philosophy

This tool embraces a **brutalist design aesthetic**:
- **High contrast**: Pure black and white base with vibrant neon accents
- **Bold typography**: Monospace fonts (JetBrains Mono, IBM Plex Mono)
- **Chunky borders**: 4px solid borders throughout
- **Sharp animations**: Snappy state changes, no subtle fades
- **Utilitarian**: Function over form, celebrating raw functionality
- **Geometric**: Grid-based layouts with asymmetric elements

## License

MIT License - Feel free to use and modify as needed.

## Support

## Contact


