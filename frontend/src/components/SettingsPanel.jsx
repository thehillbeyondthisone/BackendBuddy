import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'

export default function SettingsPanel({ onClose }) {
    const [uiScale, setUiScale] = useState(() => {
        // Load from localStorage or default to 100
        const saved = localStorage.getItem('backendbuddy_ui_scale')
        return saved ? parseInt(saved, 10) : 100
    })

    useEffect(() => {
        // Apply scale using CSS transform on root
        const root = document.getElementById('root')
        if (root) {
            const scale = uiScale / 100
            root.style.transform = `scale(${scale})`
            root.style.transformOrigin = 'top left'
            // Adjust width to compensate for scaling
            root.style.width = `${100 / scale}%`
        }
        localStorage.setItem('backendbuddy_ui_scale', uiScale.toString())
    }, [uiScale])

    // Use portal to render outside the scaled #root
    return createPortal(
        <div className="settings-overlay" onClick={onClose}>
            <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
                <div className="card-header">SETTINGS</div>

                <div className="input-group">
                    <label className="input-label">UI SCALE: {uiScale}%</label>
                    <input
                        type="range"
                        min="50"
                        max="150"
                        step="10"
                        value={uiScale}
                        onChange={(e) => setUiScale(parseInt(e.target.value, 10))}
                        className="slider"
                    />
                    <div className="flex flex-between mt-sm" style={{ fontSize: '12px', color: '#666' }}>
                        <span>50%</span>
                        <span>100%</span>
                        <span>150%</span>
                    </div>
                </div>

                <button className="btn btn-primary btn-block mt-lg" onClick={onClose}>
                    CLOSE
                </button>
            </div>
        </div>,
        document.body
    )
}


