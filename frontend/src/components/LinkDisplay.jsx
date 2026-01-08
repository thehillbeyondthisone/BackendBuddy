import { useState, useEffect } from 'react'
import axios from 'axios'

export default function LinkDisplay({ apiUrl }) {
    const [links, setLinks] = useState({ localhost: null, lan: [], ngrok: null, cloudflare: null })
    const [queueState, setQueueState] = useState({ queue_length: 0 })
    const [copiedLink, setCopiedLink] = useState(null)

    useEffect(() => {
        loadLinks()
        loadQueueState()

        const interval = setInterval(() => {
            loadLinks()
            loadQueueState()
        }, 5000)

        return () => clearInterval(interval)
    }, [])

    const loadLinks = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/links`)
            setLinks(response.data.links || {})
        } catch (error) {
            console.error('Failed to load links:', error)
        }
    }

    const loadQueueState = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/queue/status`)
            setQueueState(response.data)
        } catch (error) {
            console.error('Failed to load queue state:', error)
        }
    }

    const copyToClipboard = async (url, key) => {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(url)
            } else {
                // Fallback for non-secure contexts (LAN HTTP)
                const textArea = document.createElement("textarea")
                textArea.value = url
                textArea.style.position = "fixed"
                textArea.style.left = "-9999px"
                textArea.style.top = "0"
                document.body.appendChild(textArea)
                textArea.focus()
                textArea.select()
                try {
                    document.execCommand('copy')
                } catch (err) {
                    console.error('Fallback copy failed', err)
                }
                document.body.removeChild(textArea)
            }
            setCopiedLink(key)
            setTimeout(() => setCopiedLink(null), 2000)
        } catch (err) {
            console.error('Copy failed', err)
        }
    }

    const renderSingleLink = (type, url, key) => {
        if (!url) return null

        return (
            <div key={key || type} className="link-card">
                <div className="link-type">{type.toUpperCase()}</div>
                <div className="link-url">{url}</div>
                <button
                    className="link-copy"
                    onClick={() => copyToClipboard(url, key || type)}
                >
                    {copiedLink === (key || type) ? '✓ COPIED' : 'COPY'}
                </button>
            </div>
        )
    }

    // Check if we have any links to display
    const hasLinks = links.localhost || (links.lan && links.lan.length > 0) || links.ngrok

    return (
        <div className="card card-warning">
            <div className="card-header flex flex-between">
                <span>ACCESS LINKS</span>
                {queueState.queue_length > 0 && (
                    <span className="status-badge status-waiting">
                        {queueState.queue_length} IN QUEUE
                    </span>
                )}
            </div>

            {!hasLinks ? (
                <div style={{ textAlign: 'center', padding: 'var(--space-xl)', color: '#666' }}>
                    Configure and start your server to see access links.
                </div>
            ) : (
                <div>
                    {renderSingleLink('localhost', links.localhost)}

                    {/* Render all LAN links (auto-detected) */}
                    {links.lan && links.lan.length > 0 && links.lan.map((url, index) => (
                        renderSingleLink(`LAN ${index + 1}`, url, `lan-${index}`)
                    ))}

                    {/* Tunnel links - root redirects to /preview automatically */}
                    {links.ngrok && renderSingleLink('ngrok', links.ngrok)}
                    {links.cloudflare && renderSingleLink('cloudflare', links.cloudflare)}
                </div>
            )}

            {queueState.waiting_users && queueState.waiting_users.length > 0 && (
                <div className="mt-md">
                    <div className="input-label mb-sm">QUEUE STATUS</div>
                    <div className="queue-users">
                        {queueState.active_user && (
                            <div className="queue-user active" title="Active User">A</div>
                        )}
                        {queueState.waiting_users.map((user, index) => (
                            <div key={user.session_id} className="queue-user" title={`Position ${user.position}`}>
                                {user.position}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
