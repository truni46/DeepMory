import { useState } from 'react';
import ModeSelector from './ModeSelector';
import ConnectionStatus from './ConnectionStatus';

export default function SettingsPanel({ isOpen, onClose, settings, onSave, connectionStatus }) {
    const [localSettings, setLocalSettings] = useState(settings);

    const handleSave = () => {
        onSave(localSettings);
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
            <div
                className="bg-dark-surface border border-emerald border-opacity-20 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-bright-green">Settings</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Settings Content */}
                <div className="space-y-6">
                    {/* Communication Mode */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Communication Mode
                        </label>
                        <ModeSelector
                            mode={localSettings.communication_mode}
                            onChange={(mode) => setLocalSettings({ ...localSettings, communication_mode: mode })}
                        />
                        <p className="text-xs text-gray-500 mt-2">
                            Streaming: SSE-based (default) • WebSocket: Real-time bidirectional
                        </p>
                    </div>

                    {/* Show Timestamps */}
                    <div>
                        <label className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-300">Show Timestamps</span>
                            <input
                                type="checkbox"
                                checked={localSettings.show_timestamps}
                                onChange={(e) => setLocalSettings({ ...localSettings, show_timestamps: e.target.checked })}
                                className="w-5 h-5 text-bright-green bg-deep-forest border-gray-600 rounded focus:ring-bright-green focus:ring-2"
                            />
                        </label>
                    </div>

                    {/* Theme */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Theme
                        </label>
                        <select
                            value={localSettings.theme}
                            onChange={(e) => setLocalSettings({ ...localSettings, theme: e.target.value })}
                            className="w-full bg-deep-forest bg-opacity-50 text-gray-200 border border-emerald border-opacity-20 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-bright-green"
                        >
                            <option value="dark-green">Dark Green</option>
                            <option value="dark">Dark</option>
                            <option value="light">Light (Coming Soon)</option>
                        </select>
                    </div>

                    {/* Connection Status */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            Connection Status
                        </label>
                        <div className="bg-deep-forest bg-opacity-30 rounded-lg p-3">
                            <ConnectionStatus status={connectionStatus} />
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex space-x-3 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        className="flex-1 px-4 py-2 bg-bright-green hover:bg-emerald text-white rounded-lg transition-colors font-medium"
                    >
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
}
