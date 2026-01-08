import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export default function ServerControl({ apiUrl }) {
    const [status, setStatus] = useState({ running: false, pid: null, uptime: null })
    const [logs, setLogs] = useState([])
    const [loading, setLoading] = useState(false)
    const logsEndRef = useRef(null)
    const wsRef = useRef(null)

    useEffect(() => {
        loadStatus()
        loadLogs()
        connectWebSocket()

        const interval = setInterval(loadStatus, 3000)
        return () => {
            clearInterval(interval)
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [])

    const connectWebSocket = () => {
        const wsHost = apiUrl.replace('http://', '').replace('https://', '')
        const ws = new WebSocket(`ws://${wsHost}/ws/logs`)

        ws.onmessage = (event) => {
            setLogs(prev => [...prev.slice(-200), event.data])
        }

        wsRef.current = ws
    }

    const loadStatus = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/server/status`)
            setStatus(response.data)
        } catch (error) {
            console.error('Failed to load status:', error)
        }
    }

    const loadLogs = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/server/logs`)
            setLogs(response.data.logs || [])
        } catch (error) {
            console.error('Failed to load logs:', error)
        }
    }

    const toggleServer = async () => {
        if (loading) return

        setLoading(true)
        const action = status.running ? 'stop' : 'start'

        try {
            const response = await axios.post(`${apiUrl}/api/server`, { action })

            if (action === 'start') {
                setLogs([])
            }

            setTimeout(loadStatus, 500)
        } catch (error) {
            console.error(`Failed to ${action} server:`, error)
        } finally {
            setLoading(false)
        }
    }

    const formatUptime = (seconds) => {
        if (!seconds) return '0s'
        const hours = Math.floor(seconds / 3600)
        const minutes = Math.floor((seconds % 3600) / 60)
        const secs = seconds % 60

        if (hours > 0) return `${hours}h ${minutes}m`
        if (minutes > 0) return `${minutes}m ${secs}s`
        return `${secs}s`
    }

    return (
        <div className="card card-danger">
            <div className="card-header flex flex-between">
                <span>SERVER CONTROL</span>
                {status.running && (
                    <span style={{ color: 'var(--color-primary)', fontSize: '0.85rem' }}>
                        UPTIME: {formatUptime(status.uptime)}
                    </span>
                )}
            </div>

            {/* Big Status Button */}
            <div className={`server-toggle ${status.running ? 'running' : 'stopped'} ${loading ? 'loading' : ''}`} onClick={toggleServer}>
                <div className="server-icon">
                    {loading ? (
                        <div className="spinner-large"></div>
                    ) : (
                        <span style={{ fontSize: '1.5rem' }}>{status.running ? '⚡' : '⏻'}</span>
                    )}
                </div>
                <div className="server-info">
                    <div className="server-label">{loading ? 'PROCESSING...' : (status.running ? 'SERVER RUNNING' : 'SERVER STOPPED')}</div>
                    <div className="server-sublabel">{status.running ? 'Click to Stop' : 'Click to Start'}</div>
                </div>
            </div>

            {/* Logs Section */}
            <div className="input-label mb-sm flex flex-between mt-md">
                <span>SERVER LOGS</span>
                <button
                    className="btn-mini"
                    onClick={() => setLogs([])}
                >
                    CLEAR
                </button>
            </div>
            <div className="logs-container">
                {logs.length === 0 ? (
                    <div className="log-entry" style={{ color: '#555', fontStyle: 'italic' }}>
                        Waiting for server logs...
                    </div>
                ) : (
                    logs.map((log, index) => (
                        <div key={index} className="log-entry">{log}</div>
                    ))
                )}
                <div ref={logsEndRef} />
            </div>

            <style>{`
                .server-toggle {
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    padding: 1.5rem;
                    border-radius: 12px;
                    background: rgba(0,0,0,0.3);
                    border: 2px solid #333;
                    cursor: pointer;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    position: relative;
                    overflow: hidden;
                }
                .server-toggle:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                }
                .server-toggle:active {
                    transform: translateY(0);
                }
                .server-toggle.stopped:hover {
                    border-color: #666;
                }
                .server-toggle.running {
                    border-color: var(--color-primary);
                    background: rgba(0, 255, 157, 0.05);
                    box-shadow: 0 0 15px rgba(0, 255, 157, 0.1);
                }
                .server-toggle.running:hover {
                    box-shadow: 0 0 20px rgba(0, 255, 157, 0.2);
                }
                .server-icon {
                    width: 50px;
                    height: 50px;
                    border-radius: 50%;
                    background: #222;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.3s;
                }
                .server-toggle.running .server-icon {
                    background: var(--color-primary);
                    color: #000;
                    box-shadow: 0 0 10px var(--color-primary);
                }
                .server-info {
                    display: flex;
                    flex-direction: column;
                }
                .server-label {
                    font-weight: 800;
                    font-size: 1.1rem;
                    letter-spacing: 0.5px;
                }
                .server-sublabel {
                    font-size: 0.8rem;
                    color: #666;
                }
                .server-toggle.running .server-label {
                    color: var(--color-primary);
                }
                .spinner-large {
                    width: 24px;
                    height: 24px;
                    border: 3px solid transparent;
                    border-top-color: currentColor;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                .btn-mini {
                    background: transparent;
                    border: 1px solid #444;
                    color: #888;
                    cursor: pointer;
                    border-radius: 4px;
                    font-size: 0.7rem;
                    padding: 2px 8px;
                    transition: all 0.2s;
                }
                .btn-mini:hover {
                    border-color: #666;
                    color: #aaa;
                    background: rgba(255,255,255,0.05);
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
