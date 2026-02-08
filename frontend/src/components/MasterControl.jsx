import { useState, useEffect } from 'react'
import axios from 'axios'

export default function MasterControl({ apiUrl }) {
    const [bootState, setBootState] = useState('off') // off, booting, running
    const [bootStep, setBootStep] = useState(0)
    const [bootMessages, setBootMessages] = useState([])
    const [serverStatus, setServerStatus] = useState({ running: false })
    const [linksStatus, setLinksStatus] = useState({ ngrok: false, cloudflare: false })

    useEffect(() => {
        checkStatus()
        const interval = setInterval(checkStatus, 3000)
        return () => clearInterval(interval)
    }, [])

    const checkStatus = async () => {
        try {
            const [serverRes, linksRes, configRes] = await Promise.all([
                axios.get(`${apiUrl}/api/server/status`),
                axios.get(`${apiUrl}/api/links`),
                axios.get(`${apiUrl}/api/config`)
            ])

            setServerStatus(serverRes.data)
            const links = linksRes.data.links || {}
            setLinksStatus({
                ngrok: !!links.ngrok,
                cloudflare: !!links.cloudflare,
                config: configRes.data
            })

            // Update boot state based on actual status
            if (serverRes.data.running) {
                if (bootState !== 'booting') {
                    setBootState('running')
                }
            } else if (bootState !== 'booting') {
                setBootState('off')
            }
        } catch (error) {
            console.error('Status check failed:', error)
        }
    }

    const addMessage = (msg) => {
        setBootMessages(prev => [...prev, { time: new Date().toLocaleTimeString(), text: msg }])
    }

    const masterBoot = async () => {
        if (bootState === 'booting') return

        setBootState('booting')
        setBootStep(0)
        setBootMessages([])

        try {
            // Step 1: Initialize tunnels
            addMessage('Initializing network tunnels...')
            setBootStep(1)

            const config = linksStatus.config || {}

            if (config.ngrok_enabled) {
                addMessage('Starting ngrok tunnel...')
                await axios.post(`${apiUrl}/api/ngrok`, { action: 'start' })
                addMessage('✓ ngrok connected')
            }

            if (config.cloudflare_enabled) {
                addMessage('Starting cloudflare tunnel...')
                await axios.post(`${apiUrl}/api/cloudflare`, { action: 'start' })
                addMessage('✓ cloudflare connected')
            }

            await new Promise(r => setTimeout(r, 500))

            // Step 2: Start server
            addMessage('Starting server process...')
            setBootStep(2)

            const serverRes = await axios.post(`${apiUrl}/api/server`, { action: 'start' })

            if (serverRes.data.success) {
                addMessage(`✓ Server started (PID: ${serverRes.data.pid})`)
            } else {
                addMessage(`✗ Server failed: ${serverRes.data.message}`)
                setBootState('off')
                return
            }

            await new Promise(r => setTimeout(r, 1000))

            // Step 3: Verify
            addMessage('Verifying services...')
            setBootStep(3)

            await checkStatus()

            addMessage('✓ All systems operational!')
            setBootState('running')

        } catch (error) {
            addMessage(`✗ Boot failed: ${error.message}`)
            setBootState('off')
        }
    }

    const masterShutdown = async () => {
        if (bootState === 'booting') return

        setBootState('booting')
        setBootMessages([])

        try {
            addMessage('Shutting down server...')
            await axios.post(`${apiUrl}/api/server`, { action: 'stop' })
            addMessage('✓ Server stopped')

            addMessage('Stopping tunnels...')
            await axios.post(`${apiUrl}/api/ngrok`, { action: 'stop' })
            await axios.post(`${apiUrl}/api/cloudflare`, { action: 'stop' })
            addMessage('✓ Tunnels closed')

            setBootState('off')
            addMessage('Shutdown complete.')
        } catch (error) {
            addMessage(`Shutdown error: ${error.message}`)
            setBootState('off')
        }
    }

    const isRunning = bootState === 'running'
    const isBooting = bootState === 'booting'

    return (
        <div className="master-control">
            {/* Big Power Button */}
            <div
                className={`power-button ${bootState}`}
                onClick={isRunning ? masterShutdown : masterBoot}
            >
                <div className="power-icon">
                    {isBooting ? (
                        <div className="boot-spinner"></div>
                    ) : (
                        <span>⏻</span>
                    )}
                </div>
                <div className="power-label">
                    {isBooting ? 'BOOTING...' : (isRunning ? 'RUNNING' : 'START')}
                </div>
            </div>

            {/* Boot Progress */}
            {isBooting && (
                <div className="boot-progress">
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${(bootStep / 3) * 100}%` }}></div>
                    </div>
                </div>
            )}

            {/* Boot Messages */}
            {bootMessages.length > 0 && (
                <div className="boot-messages">
                    {bootMessages.map((msg, i) => (
                        <div key={i} className="boot-msg">
                            <span className="msg-time">{msg.time}</span>
                            <span className="msg-text">{msg.text}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Status Indicators */}
            <div className="status-row">
                <div className={`status-indicator ${serverStatus.running ? 'active' : ''}`}>
                    <span className="indicator-dot"></span>
                    <span>SERVER</span>
                </div>
                <div className={`status-indicator ${linksStatus.ngrok ? 'active' : ''}`}>
                    <span className="indicator-dot"></span>
                    <span>NGROK</span>
                </div>
                <div className={`status-indicator ${linksStatus.cloudflare ? 'active' : ''}`}>
                    <span className="indicator-dot"></span>
                    <span>CLOUDFLARE</span>
                </div>
            </div>

            <style>{`
                .master-control {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 1rem;
                    padding: 1.5rem;
                    background: rgba(0,0,0,0.4);
                    border: 2px solid #333;
                    border-radius: 12px;
                    margin-bottom: 1rem;
                }
                .power-button {
                    width: 120px;
                    height: 120px;
                    border-radius: 50%;
                    background: linear-gradient(145deg, #1a1a1a, #0a0a0a);
                    border: 4px solid #333;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    transition: all 0.3s;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                }
                .power-button:hover {
                    transform: scale(1.05);
                }
                .power-button.off:hover {
                    border-color: var(--color-primary);
                    box-shadow: 0 0 30px rgba(0, 255, 0, 0.2);
                }
                .power-button.running {
                    border-color: var(--color-primary);
                    box-shadow: 0 0 40px rgba(0, 255, 0, 0.3);
                }
                .power-button.running .power-icon {
                    color: var(--color-primary);
                    text-shadow: 0 0 20px var(--color-primary);
                }
                .power-button.booting {
                    border-color: var(--color-warning);
                    box-shadow: 0 0 30px rgba(255, 255, 0, 0.2);
                    cursor: not-allowed;
                }
                .power-icon {
                    font-size: 2.5rem;
                    color: #555;
                    transition: all 0.3s;
                }
                .power-label {
                    font-size: 0.75rem;
                    font-weight: 700;
                    color: #666;
                    margin-top: 0.25rem;
                    letter-spacing: 1px;
                }
                .power-button.running .power-label {
                    color: var(--color-primary);
                }
                .boot-spinner {
                    width: 30px;
                    height: 30px;
                    border: 3px solid transparent;
                    border-top-color: var(--color-warning);
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                .boot-progress {
                    width: 100%;
                    max-width: 200px;
                }
                .progress-bar {
                    height: 4px;
                    background: #333;
                    border-radius: 2px;
                    overflow: hidden;
                }
                .progress-fill {
                    height: 100%;
                    background: var(--color-primary);
                    transition: width 0.3s;
                }
                .boot-messages {
                    width: 100%;
                    max-height: 120px;
                    overflow-y: auto;
                    background: rgba(0,0,0,0.3);
                    border-radius: 6px;
                    padding: 0.5rem;
                    font-size: 0.75rem;
                    font-family: monospace;
                }
                .boot-msg {
                    display: flex;
                    gap: 0.5rem;
                    padding: 0.25rem 0;
                    border-bottom: 1px solid #222;
                }
                .boot-msg:last-child {
                    border-bottom: none;
                }
                .msg-time {
                    color: #555;
                    flex-shrink: 0;
                }
                .msg-text {
                    color: #aaa;
                }
                .status-row {
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                }
                .status-indicator {
                    display: flex;
                    align-items: center;
                    gap: 0.4rem;
                    font-size: 0.7rem;
                    color: #555;
                    font-weight: 600;
                }
                .indicator-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #333;
                    transition: all 0.3s;
                }
                .status-indicator.active .indicator-dot {
                    background: var(--color-primary);
                    box-shadow: 0 0 8px var(--color-primary);
                }
                .status-indicator.active {
                    color: var(--color-primary);
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    )
}
