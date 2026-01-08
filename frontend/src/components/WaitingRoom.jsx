import { useEffect, useState } from 'react'

export default function WaitingRoom({ queueStatus, onLeave }) {
    const [dots, setDots] = useState('.')

    useEffect(() => {
        const interval = setInterval(() => {
            setDots(prev => prev.length >= 3 ? '.' : prev + '.')
        }, 500)

        return () => clearInterval(interval)
    }, [])

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--color-bg)'
        }}>
            <div className="card card-warning" style={{ maxWidth: '600px', width: '90%' }}>
                <div className="card-header text-center">WAITING ROOM</div>

                <div className="queue-position">
                    POSITION: {queueStatus?.position || '?'}
                </div>

                <div className="text-center mb-lg" style={{ fontSize: 'var(--font-size-lg)', color: 'var(--color-warning)' }}>
                    <span className="blink">●</span> WAITING FOR ACCESS{dots}
                </div>

                <div className="card" style={{ background: 'var(--color-text)', color: 'var(--color-text-inverse)', marginBottom: 'var(--space-lg)' }}>
                    <div style={{ marginBottom: 'var(--space-sm)' }}>
                        <strong style={{ color: 'var(--color-primary)' }}>STATUS:</strong> {queueStatus?.message || 'In queue'}
                    </div>
                    {queueStatus?.position && queueStatus.position > 1 && (
                        <div>
                            <strong style={{ color: 'var(--color-primary)' }}>USERS AHEAD:</strong> {queueStatus.position - 1}
                        </div>
                    )}
                </div>

                <div className="text-center mb-md" style={{ fontSize: 'var(--font-size-sm)', color: '#999' }}>
                    You will be automatically redirected when it's your turn.
                </div>

                <button
                    className="btn btn-danger btn-block"
                    onClick={onLeave}
                >
                    LEAVE QUEUE
                </button>
            </div>
        </div>
    )
}
