import { useState, useEffect } from 'react'
import ProjectConfig from './components/ProjectConfig'
import MasterControl from './components/MasterControl'
import ServerControl from './components/ServerControl'
import LinkControl from './components/LinkControl'
import LinkDisplay from './components/LinkDisplay'
import WaitingRoom from './components/WaitingRoom'
import InstructionsPanel from './components/InstructionsPanel'
import SettingsPanel from './components/SettingsPanel'
import NetworkMonitor from './components/NetworkMonitor'
import axios from 'axios'

// Use dynamic hostname for LAN access (fallback to localhost if undefined, e.g. during build)
const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost'
const protocol = typeof window !== 'undefined' ? window.location.protocol : 'http:'
const API_URL = `${protocol}//${hostname}:1338`

function App() {
    const [sessionId, setSessionId] = useState(null)
    const [queueStatus, setQueueStatus] = useState(null)
    const [isInWaitingRoom, setIsInWaitingRoom] = useState(false)
    const [showSettings, setShowSettings] = useState(false)

    useEffect(() => {
        // Check if we need to join queue
        checkQueueAccess()

        // Apply saved UI scale on load using CSS transform
        const savedScale = localStorage.getItem('backendbuddy_ui_scale')
        if (savedScale) {
            const root = document.getElementById('root')
            if (root) {
                const scale = parseInt(savedScale, 10) / 100
                root.style.transform = `scale(${scale})`
                root.style.transformOrigin = 'top left'
                root.style.width = `${100 / scale}%`
            }
        }
    }, [])

    const checkQueueAccess = async () => {
        try {
            const response = await axios.post(`${API_URL}/api/queue/join`, {
                session_id: sessionId
            })

            const newSessionId = response.data.session_id
            setSessionId(newSessionId)

            if (response.data.status === 'waiting') {
                setIsInWaitingRoom(true)
                setQueueStatus(response.data)
                startHeartbeat(newSessionId)
            } else {
                setIsInWaitingRoom(false)
            }
        } catch (error) {
            console.error('Failed to join queue:', error)
        }
    }

    const startHeartbeat = (sid) => {
        const interval = setInterval(async () => {
            try {
                const response = await axios.post(`${API_URL}/api/queue/heartbeat`, {
                    session_id: sid
                })

                if (response.data.status === 'active') {
                    setIsInWaitingRoom(false)
                    clearInterval(interval)
                } else {
                    // Update queue position
                    const statusResponse = await axios.get(`${API_URL}/api/queue/my-status/${sid}`)
                    setQueueStatus(statusResponse.data)
                }
            } catch (error) {
                console.error('Heartbeat failed:', error)
            }
        }, 5000) // Every 5 seconds

        return () => clearInterval(interval)
    }

    const leaveQueue = async () => {
        if (sessionId) {
            try {
                await axios.post(`${API_URL}/api/queue/leave`, {
                    session_id: sessionId
                })
                setIsInWaitingRoom(false)
                setQueueStatus(null)
            } catch (error) {
                console.error('Failed to leave queue:', error)
            }
        }
    }

    if (isInWaitingRoom) {
        return <WaitingRoom queueStatus={queueStatus} onLeave={leaveQueue} />
    }

    return (
        <>
            {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}

            {/* Floating Network Monitor */}
            <NetworkMonitor apiUrl={API_URL} />

            <div>
                <button className="settings-gear" onClick={() => setShowSettings(true)}>
                    ⚙
                </button>

                <header className="app-header">
                    <h1 className="app-title">BACKEND_BUDDY</h1>
                </header>

                <div className="container">
                    <div className="grid grid-2">
                        <div>
                            <ProjectConfig apiUrl={API_URL} />
                        </div>
                        <div>
                            <MasterControl apiUrl={API_URL} />
                            <LinkControl apiUrl={API_URL} />
                            <div className="mt-md">
                                <ServerControl apiUrl={API_URL} />
                            </div>
                        </div>
                    </div>

                    <div className="mt-lg">
                        <InstructionsPanel />
                    </div>
                </div>
            </div>
        </>
    )
}

export default App
