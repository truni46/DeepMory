import { useState } from 'react';
import SimpleMDE from 'react-simplemde-editor';
import 'easymde/dist/easymde.min.css';
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
        <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
            <div
                className="bg-white rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl animate-fade-in flex flex-col max-h-[85vh]"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-primary">Settings</h2>
                    <button
                        onClick={onClose}
                        className="text-text-muted hover:text-text-primary transition-colors p-1 rounded-full hover:bg-bg-secondary"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Settings Content */}
                <div className="space-y-6 overflow-y-auto custom-scrollbar flex-1 pr-2">
                    {/* Communication Mode */}
                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">
                            Communication Mode
                        </label>
                        <ModeSelector
                            mode={localSettings.communication_mode}
                            onChange={(mode) => setLocalSettings({ ...localSettings, communication_mode: mode })}
                        />
                        <p className="text-xs text-text-muted mt-2">
                            Streaming: SSE-based (default) • WebSocket: Real-time bidirectional
                        </p>
                    </div>

                    {/* Show Timestamps */}
                    <div>
                        <label className="flex items-center justify-between cursor-pointer group">
                            <span className="text-sm font-medium text-text-primary group-hover:text-primary transition-colors">Show Timestamps</span>
                            <div className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={localSettings.show_timestamps}
                                    onChange={(e) => setLocalSettings({ ...localSettings, show_timestamps: e.target.checked })}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                            </div>
                        </label>
                    </div>

                    {/* Welcome Message */}
                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">
                            Welcome Message
                        </label>
                        <div className="prose prose-sm max-w-none border rounded-lg overflow-hidden">
                            <SimpleMDE
                                value={localSettings.welcome_message || ''}
                                onChange={(value) => setLocalSettings({ ...localSettings, welcome_message: value })}
                                options={{
                                    spellChecker: false,
                                    maxHeight: "150px",
                                    status: false,
                                    toolbar: ["bold", "italic", "heading", "|", "quote", "code", "unordered-list", "ordered-list", "|", "preview", "guide"],
                                }}
                            />
                        </div>
                        <p className="text-xs text-text-muted mt-1">
                            Customize the initial greeting message.
                        </p>
                    </div>

                    {/* Theme */}
                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">
                            Theme
                        </label>
                        <select
                            value={localSettings.theme}
                            onChange={(e) => setLocalSettings({ ...localSettings, theme: e.target.value })}
                            className="w-full bg-bg-secondary text-text-primary border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        >
                            <option value="light-green">Light Green (Default)</option>
                            <option value="dark">Dark (Coming Soon)</option>
                        </select>
                    </div>

                    {/* Connection Status */}
                    <div>
                        <label className="block text-sm font-medium text-text-secondary mb-2">
                            Connection Status
                        </label>
                        <div className="bg-bg-secondary rounded-lg p-3 border border-border">
                            <ConnectionStatus status={connectionStatus} />
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex space-x-3 mt-8">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-white border border-border text-text-secondary hover:bg-bg-secondary rounded-lg transition-colors font-medium"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        className="flex-1 px-4 py-2 bg-primary hover:bg-primary-dark text-white rounded-lg transition-colors font-medium shadow-sm hover:shadow-md"
                    >
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
}
