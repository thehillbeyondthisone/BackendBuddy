import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import axios from 'axios'

export default function NetworkMonitor({ apiUrl }) {
    const [isOpen, setIsOpen] = useState(false)
    const [activeTab, setActiveTab] = useState('live')
    const [metrics, setMetrics] = useState(null)
    const [requests, setRequests] = useState([])
    const [endpoints, setEndpoints] = useState([])
    const [connections, setConnections] = useState([])
    const wsRef = useRef(null)
    const liveListRef = useRef(null)

    useEffect(() => {
        if (isOpen) {
            loadData()
            connectWebSocket()
            const interval = setInterval(loadMetrics, 2000)
            return () => {
                clearInterval(interval)
                if (wsRef.current) {
                    wsRef.current.close()
                }
            }
        }
    }, [isOpen])

    // Removed auto-scroll - user prefers manual control

    const loadData = async () => {
        await Promise.all([loadMetrics(), loadRequests(), loadEndpoints(), loadConnections()])
    }

    const loadMetrics = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/traffic/metrics`)
            setMetrics(response.data)
        } catch (error) {
            console.error('Failed to load metrics:', error)
        }
    }

    const loadRequests = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/traffic/requests?count=100`)
            setRequests(response.data.requests || [])
        } catch (error) {
            console.error('Failed to load requests:', error)
        }
    }

    const loadEndpoints = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/traffic/endpoints`)
            setEndpoints(response.data.endpoints || [])
        } catch (error) {
            console.error('Failed to load endpoints:', error)
        }
    }

    const loadConnections = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/traffic/connections`)
            setConnections(response.data.connections || [])
        } catch (error) {
            console.error('Failed to load connections:', error)
        }
    }

    const connectWebSocket = () => {
        const wsHost = apiUrl.replace('http://', '').replace('https://', '')
        const ws = new WebSocket(`ws://${wsHost}/ws/traffic`)

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            setRequests(prev => [data, ...prev.slice(0, 99)])
        }

        ws.onerror = (error) => {
            console.error('Traffic WebSocket error:', error)
        }

        wsRef.current = ws
    }

    const clearData = async () => {
        try {
            await axios.delete(`${apiUrl}/api/traffic/clear`)
            setRequests([])
            setEndpoints([])
            loadMetrics()
        } catch (error) {
            console.error('Failed to clear traffic data:', error)
        }
    }

    const formatBytes = (bytes) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / 1024 / 1024).toFixed(2)} MB`
    }

    const formatTime = (timestamp) => {
        return new Date(timestamp).toLocaleTimeString()
    }

    const getStatusClass = (status) => {
        if (status >= 500) return 'status-5xx'
        if (status >= 400) return 'status-4xx'
        if (status >= 300) return 'status-3xx'
        return 'status-2xx'
    }

    const getMethodClass = (method) => {
        return `method-${method.toLowerCase()}`
    }

    if (!isOpen) {
        return createPortal(
            <button
                className="network-monitor-toggle"
                onClick={() => setIsOpen(true)}
                title="Network Monitor"
            >
                📡 NETWORK
            </button>,
            document.body
        )
    }

    return createPortal(
        <div className="network-monitor-popout">
            <div className="network-monitor-header">
                <span>📡 NETWORK MONITOR</span>
                <div className="flex flex-gap">
                    <button className="btn" onClick={clearData} style={{ padding: '4px 8px', fontSize: '10px' }}>
                        CLEAR
                    </button>
                    <button className="btn btn-danger" onClick={() => setIsOpen(false)} style={{ padding: '4px 8px', fontSize: '10px' }}>
                        ✕
                    </button>
                </div>
            </div>

            {/* Metrics Row */}
            {metrics && (
                <div className="metrics-row">
                    <div className="metric-card">
                        <div className="metric-value">{metrics.total_requests}</div>
                        <div className="metric-label">REQUESTS</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-value">{metrics.requests_per_second}</div>
                        <div className="metric-label">REQ/SEC</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-value">{metrics.avg_latency_ms}ms</div>
                        <div className="metric-label">AVG LATENCY</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-value" style={{ color: metrics.error_rate > 0 ? 'var(--color-danger)' : 'inherit' }}>
                            {metrics.error_rate}%
                        </div>
                        <div className="metric-label">ERROR RATE</div>
                    </div>
                    <div className="metric-card">
                        <div className="metric-value">{metrics.active_connections}</div>
                        <div className="metric-label">CONNECTIONS</div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="monitor-tabs">
                <button
                    className={`tab-btn ${activeTab === 'live' ? 'active' : ''}`}
                    onClick={() => setActiveTab('live')}
                >
                    LIVE FEED
                </button>
                <button
                    className={`tab-btn ${activeTab === 'endpoints' ? 'active' : ''}`}
                    onClick={() => { setActiveTab('endpoints'); loadEndpoints(); }}
                >
                    ENDPOINTS
                </button>
                <button
                    className={`tab-btn ${activeTab === 'connections' ? 'active' : ''}`}
                    onClick={() => { setActiveTab('connections'); loadConnections(); }}
                >
                    CONNECTIONS
                </button>
            </div>

            {/* Tab Content */}
            <div className="monitor-content">
                {activeTab === 'live' && (
                    <div className="live-feed" ref={liveListRef}>
                        {requests.length === 0 ? (
                            <div className="no-data">No requests yet. Generate some traffic!</div>
                        ) : (
                            requests.map((req, index) => (
                                <div key={index} className="request-row">
                                    <span className={`method-badge ${getMethodClass(req.method)}`}>
                                        {req.method}
                                    </span>
                                    <span className={`status-badge ${getStatusClass(req.status)}`}>
                                        {req.status}
                                    </span>
                                    <span className="request-path">{req.path}</span>
                                    <span className="request-latency">{req.latency_ms}ms</span>
                                    <span className="request-time">{formatTime(req.timestamp)}</span>
                                </div>
                            ))
                        )}
                    </div>
                )}

                {activeTab === 'endpoints' && (
                    <div className="endpoints-table">
                        {endpoints.length === 0 ? (
                            <div className="no-data">No endpoint data yet.</div>
                        ) : (
                            <table>
                                <thead>
                                    <tr>
                                        <th>ENDPOINT</th>
                                        <th>COUNT</th>
                                        <th>ERRORS</th>
                                        <th>AVG LATENCY</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {endpoints.map((ep, index) => (
                                        <tr key={index}>
                                            <td>
                                                <span className={`method-badge ${getMethodClass(ep.method)}`}>
                                                    {ep.method}
                                                </span>
                                                {ep.path}
                                            </td>
                                            <td>{ep.count}</td>
                                            <td style={{ color: ep.errors > 0 ? 'var(--color-danger)' : 'inherit' }}>
                                                {ep.errors}
                                            </td>
                                            <td>{ep.avg_latency_ms}ms</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}

                {activeTab === 'connections' && (
                    <div className="connections-list">
                        {connections.length === 0 ? (
                            <div className="no-data">No active connections.</div>
                        ) : (
                            connections.map((conn, index) => (
                                <div key={index} className="connection-row">
                                    <span className="conn-type">{conn.type.toUpperCase()}</span>
                                    <span className="conn-client">{conn.client}</span>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </div>
        </div>,
        document.body
    )
}
