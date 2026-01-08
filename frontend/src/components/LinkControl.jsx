import { useState, useEffect } from 'react'
import axios from 'axios'

export default function LinkControl({ apiUrl }) {
    const [links, setLinks] = useState({
        localhost: null,
        lan: [],
        ngrok: null,
        cloudflare: null
    })
    const [loading, setLoading] = useState({ ngrok: false, cloudflare: false })
    const [copiedLink, setCopiedLink] = useState(null)
    const [serverRunning, setServerRunning] = useState(false)

    useEffect(() => {
        loadAll()
        const interval = setInterval(loadAll, 5000)
        return () => clearInterval(interval)
    }, [])

    const loadAll = async () => {
        // Parallel checks for responsiveness
        loadLinksStatus()
        checkServerStatus()
    }

    const checkServerStatus = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/server/status`)
            setServerRunning(response.data.running)
        } catch (error) {
            console.error('Failed to check server status:', error)
        }
    }

    const loadLinksStatus = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/links`)
            setLinks(response.data.links || {})
        } catch (error) {
            console.error('Failed to load links status:', error)
        }
    }

    const toggleTunnel = async (type) => {
        if (loading[type]) return

        setLoading(prev => ({ ...prev, [type]: true }))
        const isActive = type === 'ngrok' ? !!links.ngrok : !!links.cloudflare
        const action = isActive ? 'stop' : 'start'

        try {
            await axios.post(`${apiUrl}/api/${type}`, { action })
            setTimeout(loadLinksStatus, 500)
        } catch (error) {
            console.error(`Failed to ${action} ${type}:`, error)
        } finally {
            setLoading(prev => ({ ...prev, [type]: false }))
        }
    }

    const copyToClipboard = async (url, key) => {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(url)
            } else {
                const textArea = document.createElement("textarea")
                textArea.value = url
                textArea.style.cssText = "position:fixed;left:-9999px"
                document.body.appendChild(textArea)
                textArea.select()
                document.execCommand('copy')
                document.body.removeChild(textArea)
            }
            setCopiedLink(key)
            setTimeout(() => setCopiedLink(null), 2000)
        } catch (err) {
            console.error('Copy failed', err)
        }
    }

    const tunnelsActive = !!links.ngrok || !!links.cloudflare
    const hasAnyLinks = links.localhost || links.lan?.length || tunnelsActive

    const renderLink = (type, url, key, color = '#888', delay = 0) => (
        <div
            key={key}
            className="link-card link-animate"
            style={{
                borderLeft: `3px solid ${color}`,
                animationDelay: `${delay}ms`
            }}
        >
            <div className="link-type" style={{ color }}>{type.toUpperCase()}</div>
            <div className="link-url">{url}</div>
            <button
                className="link-copy"
                onClick={() => copyToClipboard(url, key)}
            >
                {copiedLink === key ? '✓ COPIED' : 'COPY'}
            </button>
        </div>
    )

    const TunnelButton = ({ type, label, color, isActive, isLoading }) => (
        <div
            className={`tunnel-btn ${isActive ? 'active' : ''} ${isLoading ? 'loading' : ''}`}
            onClick={() => toggleTunnel(type)}
            style={{ '--btn-color': color }}
        >
            <div className="tunnel-icon">
                {isLoading ? <div className="spinner-mini"></div> : (isActive ? '●' : '○')}
            </div>
            <div className="tunnel-info">
                <div className="tunnel-label">{label}</div>
                <div className="tunnel-status">{isLoading ? 'Loading...' : (isActive ? 'Active' : 'Offline')}</div>
            </div>
        </div>
    )

    return (
        <div className="card card-warning">
            <div className="card-header flex flex-between">
                <span>NETWORK TUNNELS</span>
            </div>

            {/* Tunnel Buttons */}
            <div className="tunnels-row mb-md">
                <TunnelButton
                    type="ngrok"
                    label="NGROK"
                    color="var(--color-primary)"
                    isActive={!!links.ngrok}
                    isLoading={loading.ngrok}
                />
                <TunnelButton
                    type="cloudflare"
                    label="CLOUDFLARE"
                    color="var(--color-info)"
                    isActive={!!links.cloudflare}
                    isLoading={loading.cloudflare}
                />
            </div>

            {/* Links Section */}
            {hasAnyLinks && (
                <div className="links-section">
                    <div className="input-label mb-sm">AVAILABLE LINKS</div>
                    <div className="links-list">
                        {links.localhost && renderLink('localhost', links.localhost, 'localhost', '#666', 0)}
                        {links.lan?.map((lanUrl, idx) =>
                            renderLink('lan', lanUrl, `lan-${idx}`, '#6a9', 50 * (idx + 1))
                        )}
                        {links.ngrok && renderLink('ngrok', links.ngrok, 'ngrok', 'var(--color-primary)', 100)}
                        {links.cloudflare && renderLink('cloudflare', links.cloudflare, 'cloudflare', 'var(--color-info)', 150)}
                    </div>
                </div>
            )}

            {/* Empty state */}
            {!hasAnyLinks && (
                <div style={{ color: '#555', fontStyle: 'italic', padding: '0.5rem', textAlign: 'center' }}>
                    Start server to detect local links.
                </div>
            )}

            <style>{`
                .tunnels-row {
                    display: flex;
                    gap: 1rem;
                }
                .tunnel-btn {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    padding: 0.75rem;
                    background: rgba(0,0,0,0.3);
                    border: 1px solid #444;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.2s;
                    position: relative;
                    overflow: hidden;
                }
                .tunnel-btn:hover {
                    background: rgba(255,255,255,0.05);
                    border-color: #666;
                }
                .tunnel-btn.active {
                    border-color: var(--btn-color);
                    background: rgba(0,0,0,0.4);
                    box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
                }
                .tunnel-btn.active:before {
                    content: '';
                    position: absolute;
                    top: 0;
                    bottom: 0;
                    left: 0;
                    width: 3px;
                    background: var(--btn-color);
                }
                .tunnel-icon {
                    width: 20px;
                    display: flex;
                    justify-content: center;
                    color: #666;
                    font-size: 1.2rem;
                }
                .tunnel-btn.active .tunnel-icon {
                    color: var(--btn-color);
                    text-shadow: 0 0 8px var(--btn-color);
                }
                .tunnel-info {
                    display: flex;
                    flex-direction: column;
                }
                .tunnel-label {
                    font-weight: 700;
                    font-size: 0.85rem;
                    letter-spacing: 0.5px;
                }
                .tunnel-status {
                    font-size: 0.7rem;
                    color: #777;
                }
                .tunnel-btn.active .tunnel-status {
                    color: var(--btn-color);
                }
                .spinner-mini {
                    width: 14px;
                    height: 14px;
                    border: 2px solid transparent;
                    border-top-color: currentColor;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                .links-section {
                    animation: slideIn 0.3s ease-out;
                }
                .links-list {
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                }
                .link-animate {
                    animation: fadeSlideIn 0.3s ease-out backwards;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                @keyframes slideIn {
                    from { opacity: 0; transform: translateY(-10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeSlideIn {
                    from { opacity: 0; transform: translateX(-10px); }
                    to { opacity: 1; transform: translateX(0); }
                }
            `}</style>
        </div>
    )
}
