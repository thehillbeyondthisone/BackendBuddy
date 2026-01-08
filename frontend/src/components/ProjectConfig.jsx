import { useState, useEffect } from 'react'
import axios from 'axios'

export default function ProjectConfig({ apiUrl }) {
    const [config, setConfig] = useState({
        directory: '',
        command: '',
        port: 3000,
        frontend_directory: '',
        frontend_command: ''
    })
    const [presets, setPresets] = useState([])
    const [presetName, setPresetName] = useState('')
    const [loading, setLoading] = useState(false)
    const [scanning, setScanning] = useState(false)
    const [status, setStatus] = useState(null)
    const [showAdvanced, setShowAdvanced] = useState(false)

    useEffect(() => {
        loadConfig()
        loadPresets()
    }, [])

    const loadConfig = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/config`)
            setConfig(response.data)
            if (response.data.frontend_directory || response.data.frontend_command) {
                setShowAdvanced(true)
            }
        } catch (error) {
            console.error('Failed to load config:', error)
        }
    }

    const loadPresets = async () => {
        try {
            const response = await axios.get(`${apiUrl}/api/presets`)
            setPresets(response.data || [])
        } catch (error) {
            console.error('Failed to load presets:', error)
        }
    }

    const handleChange = (e) => {
        const { name, value } = e.target
        setConfig(prev => ({ ...prev, [name]: value }))
    }

    const handleSave = async () => {
        setLoading(true)
        setStatus(null)
        try {
            const payload = { ...config, port: parseInt(config.port, 10) }
            await axios.put(`${apiUrl}/api/config`, payload)
            setStatus({ type: 'success', message: 'SAVED' })
            setTimeout(() => setStatus(null), 2000)
        } catch (error) {
            setStatus({ type: 'error', message: 'SAVE FAILED' })
        } finally {
            setLoading(false)
        }
    }

    const handleScan = async () => {
        setScanning(true)
        setStatus(null)
        try {
            const response = await axios.get(`${apiUrl}/api/scan`)
            if (response.data.success) {
                setConfig(prev => ({
                    ...prev,
                    directory: response.data.directory || prev.directory,
                    command: response.data.command || prev.command,
                    port: response.data.port || prev.port,
                    frontend_directory: response.data.frontend_directory || '',
                    frontend_command: response.data.frontend_command || ''
                }))
                setStatus({ type: 'success', message: 'PROJECT DETECTED' })
            } else {
                setStatus({ type: 'error', message: response.data.message || 'SCAN FAILED' })
            }
        } catch (error) {
            setStatus({ type: 'error', message: 'SCAN FAILED' })
        } finally {
            setScanning(false)
        }
    }

    const savePreset = async () => {
        if (!presetName.trim()) {
            setStatus({ type: 'error', message: 'ENTER PRESET NAME' })
            return
        }
        try {
            await axios.post(`${apiUrl}/api/presets`, { name: presetName })
            setStatus({ type: 'success', message: `SAVED "${presetName.toUpperCase()}"` })
            setPresetName('')
            loadPresets()
        } catch (error) {
            setStatus({ type: 'error', message: 'FAILED TO SAVE PRESET' })
        }
    }

    const loadPreset = async (id) => {
        try {
            setStatus({ type: 'info', message: 'STOPPING SERVICES...' })
            await axios.post(`${apiUrl}/api/server`, { action: 'stop' }).catch(() => { })
            await axios.post(`${apiUrl}/api/ngrok`, { action: 'stop' }).catch(() => { })
            await axios.post(`${apiUrl}/api/cloudflare`, { action: 'stop' }).catch(() => { })

            await axios.post(`${apiUrl}/api/presets/${id}/load`)
            await loadConfig()
            setStatus({ type: 'success', message: 'PRESET LOADED' })
        } catch (error) {
            setStatus({ type: 'error', message: 'FAILED TO LOAD PRESET' })
        }
    }

    const deletePreset = async (id, name) => {
        if (!confirm(`DELETE "${name}"?`)) return
        try {
            await axios.delete(`${apiUrl}/api/presets/${id}`)
            loadPresets()
        } catch (error) {
            setStatus({ type: 'error', message: 'DELETE FAILED' })
        }
    }

    return (
        <div className="card card-primary">
            <div className="card-header">PROJECT_CONFIG</div>

            {/* Saved Presets */}
            {presets.length > 0 && (
                <div className="input-group">
                    <label className="input-label">SAVED_PROJECTS</label>
                    <div className="preset-list">
                        {presets.map(preset => (
                            <div key={preset.id} className="preset-item">
                                <div className="preset-click" onClick={() => loadPreset(preset.id)}>
                                    <span className="preset-arrow">▶</span>
                                    <span className="preset-name">{preset.name}</span>
                                </div>
                                <button className="preset-del" onClick={() => deletePreset(preset.id, preset.name)}>×</button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Directory */}
            <div className="input-group">
                <label className="input-label">DIRECTORY</label>
                <input
                    type="text"
                    className="input-field"
                    name="directory"
                    value={config.directory || ''}
                    onChange={handleChange}
                    placeholder="C:\PATH\TO\PROJECT"
                />
            </div>

            {/* Command + Port */}
            <div className="flex flex-gap">
                <div style={{ flex: 1 }}>
                    <div className="input-group">
                        <label className="input-label">COMMAND</label>
                        <input
                            type="text"
                            className="input-field"
                            name="command"
                            value={config.command || ''}
                            onChange={handleChange}
                            placeholder="node server.js"
                        />
                    </div>
                </div>
                <div style={{ width: '100px' }}>
                    <div className="input-group">
                        <label className="input-label">PORT</label>
                        <input
                            type="number"
                            className="input-field"
                            name="port"
                            value={config.port || ''}
                            onChange={handleChange}
                        />
                    </div>
                </div>
            </div>

            {/* Advanced Toggle */}
            <div className="input-group">
                <label
                    className="input-label toggle-label"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                >
                    {showAdvanced ? '[-]' : '[+]'} SECONDARY_PROCESS
                </label>
                {showAdvanced && (
                    <div className="advanced-box">
                        <div className="input-group">
                            <label className="input-label-small">FRONTEND_DIR</label>
                            <input
                                type="text"
                                className="input-field"
                                name="frontend_directory"
                                value={config.frontend_directory || ''}
                                onChange={handleChange}
                            />
                        </div>
                        <div className="input-group">
                            <label className="input-label-small">FRONTEND_CMD</label>
                            <input
                                type="text"
                                className="input-field"
                                name="frontend_command"
                                value={config.frontend_command || ''}
                                onChange={handleChange}
                            />
                        </div>
                    </div>
                )}
            </div>

            {/* Save as Preset */}
            <div className="input-group">
                <label className="input-label">SAVE_AS_PRESET</label>
                <div className="flex flex-gap">
                    <input
                        type="text"
                        className="input-field"
                        style={{ flex: 1 }}
                        value={presetName}
                        onChange={(e) => setPresetName(e.target.value)}
                        placeholder="MY_PROJECT"
                    />
                    <button className="btn" onClick={savePreset}>💾</button>
                </div>
            </div>

            {/* Status */}
            {status && (
                <div className={`status-bar ${status.type}`}>
                    {status.message}
                </div>
            )}

            {/* Actions */}
            <div className="flex flex-gap mt-md">
                <button className="btn btn-warning" onClick={handleScan} disabled={scanning} style={{ flex: 1 }}>
                    {scanning ? 'SCANNING...' : '⚡ SCAN'}
                </button>
                <button className="btn btn-primary" onClick={handleSave} disabled={loading} style={{ flex: 1 }}>
                    {loading ? 'SAVING...' : '✓ APPLY'}
                </button>
            </div>

            <style>{`
                .preset-list {
                    display: flex;
                    flex-direction: column;
                    border: 2px solid var(--color-text);
                }
                .preset-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid var(--color-text);
                }
                .preset-item:last-child {
                    border-bottom: none;
                }
                .preset-click {
                    flex: 1;
                    padding: 8px 12px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    cursor: pointer;
                    transition: all 0.1s;
                }
                .preset-click:hover {
                    background: var(--color-primary);
                }
                .preset-arrow {
                    color: var(--color-primary);
                    font-size: 10px;
                }
                .preset-click:hover .preset-arrow {
                    color: var(--color-text);
                }
                .preset-name {
                    font-weight: 700;
                    text-transform: uppercase;
                }
                .preset-del {
                    background: none;
                    border: none;
                    border-left: 1px solid var(--color-text);
                    padding: 8px 12px;
                    font-size: 16px;
                    cursor: pointer;
                    color: var(--color-text);
                }
                .preset-del:hover {
                    background: var(--color-danger);
                    color: var(--color-text-inverse);
                }
                .toggle-label {
                    cursor: pointer;
                    user-select: none;
                }
                .toggle-label:hover {
                    color: var(--color-primary);
                }
                .advanced-box {
                    border-left: 4px solid var(--color-text);
                    padding-left: 12px;
                    margin-top: 8px;
                }
                .input-label-small {
                    font-size: 11px;
                    font-weight: 700;
                    text-transform: uppercase;
                    margin-bottom: 4px;
                }
                .status-bar {
                    padding: 8px;
                    text-align: center;
                    font-weight: 700;
                    border: 2px solid var(--color-text);
                    margin-top: 12px;
                }
                .status-bar.success {
                    background: var(--color-primary);
                }
                .status-bar.error {
                    background: var(--color-danger);
                    color: var(--color-text-inverse);
                }
                .status-bar.info {
                    background: var(--color-warning);
                }
            `}</style>
        </div>
    )
}
