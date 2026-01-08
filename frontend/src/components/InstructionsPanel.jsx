import { useState } from 'react'

export default function InstructionsPanel() {
    const [isOpen, setIsOpen] = useState(false)

    return (
        <div className="card mb-lg" style={{ borderColor: 'var(--color-info)' }}>
            <div
                className="card-header flex flex-between"
                style={{ cursor: 'pointer', userSelect: 'none' }}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span>📖 HOW TO USE</span>
                <span style={{
                    fontWeight: 700,
                    fontSize: 'var(--font-size-lg)',
                    transition: 'transform 0.2s',
                    transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)'
                }}>
                    ▼
                </span>
            </div>

            {isOpen && (
                <div style={{
                    padding: 'var(--space-md)',
                    background: 'var(--color-text)',
                    color: 'var(--color-text-inverse)',
                    fontSize: 'var(--font-size-sm)'
                }}>
                    <div style={{ marginBottom: 'var(--space-md)' }}>
                        <strong style={{ color: 'var(--color-primary)' }}>1. CONFIGURE YOUR PROJECT</strong>
                        <ul style={{ marginTop: 'var(--space-xs)', paddingLeft: 'var(--space-lg)' }}>
                            <li><strong>Project Directory:</strong> Full path to your project folder</li>
                            <li><strong>Server Command:</strong> e.g., <code>npm run dev</code> or <code>python -m http.server</code></li>
                            <li><strong>Port:</strong> The port YOUR project runs on (not this tool)</li>
                        </ul>
                    </div>

                    <div style={{ marginBottom: 'var(--space-md)' }}>
                        <strong style={{ color: 'var(--color-primary)' }}>2. START YOUR SERVER</strong>
                        <ul style={{ marginTop: 'var(--space-xs)', paddingLeft: 'var(--space-lg)' }}>
                            <li>Click <strong>SAVE CONFIG</strong> to save your settings</li>
                            <li>Click <strong>START</strong> to launch your dev server</li>
                            <li>Watch real-time logs in the Server Control panel</li>
                        </ul>
                    </div>

                    <div style={{ marginBottom: 'var(--space-md)' }}>
                        <strong style={{ color: 'var(--color-primary)' }}>3. SHARE YOUR PROJECT</strong>
                        <ul style={{ marginTop: 'var(--space-xs)', paddingLeft: 'var(--space-lg)' }}>
                            <li><strong>LAN Sharing:</strong> Enable to share on local network (IPs auto-detected)</li>
                            <li><strong>ngrok:</strong> Enable for a public URL anyone can access</li>
                            <li>Links appear in the ACCESS LINKS panel below</li>
                        </ul>
                    </div>

                    <div style={{ marginBottom: 'var(--space-md)' }}>
                        <strong style={{ color: 'var(--color-primary)' }}>4. AFTER CODE CHANGES</strong>
                        <ul style={{ marginTop: 'var(--space-xs)', paddingLeft: 'var(--space-lg)' }}>
                            <li>Click <strong>RESTART</strong> to stop and relaunch with same settings</li>
                            <li>No need to manually close windows or reconfigure</li>
                        </ul>
                    </div>

                    <div style={{
                        borderTop: '2px solid var(--color-info)',
                        paddingTop: 'var(--space-md)',
                        marginTop: 'var(--space-md)'
                    }}>
                        <strong style={{ color: 'var(--color-warning)' }}>⚡ WAITING ROOM QUEUE</strong>
                        <p style={{ marginTop: 'var(--space-xs)' }}>
                            When enabled, only one remote user can access at a time.
                            Others wait in queue and auto-promote when the active user leaves.
                            Local access always bypasses the queue.
                        </p>
                    </div>
                </div>
            )}
        </div>
    )
}
