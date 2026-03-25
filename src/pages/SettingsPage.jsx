import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import apiService from '../services/apiService';
import memoryService from '../services/memoryService';
import SimpleMDE from 'react-simplemde-editor';
import 'easymde/dist/easymde.min.css';
import ModeSelector from '../components/ModeSelector';
import ConnectionStatus from '../components/ConnectionStatus';
import logger from '../utils/logger';

const TABS = [
    { id: 'general', label: 'General', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
    { id: 'memory', label: 'Memory', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
    { id: 'profile', label: 'Profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
    { id: 'appearance', label: 'Appearance', icon: 'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01' },
    { id: 'connection', label: 'Connection', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
];

export default function SettingsPage() {
    const { user } = useAuth();
    const context = useOutletContext();
    const [activeTab, setActiveTab] = useState('general');
    const [settings, setSettings] = useState({
        communication_mode: 'websocket',
        show_timestamps: true,
        theme: 'light-green',
        welcome_message: '',
    });
    const [saved, setSaved] = useState(false);

    // Memory state
    const [memoryEnabled, setMemoryEnabled] = useState(true);
    const [memories, setMemories] = useState([]);
    const [memoriesLoading, setMemoriesLoading] = useState(false);
    const [editingMemoryId, setEditingMemoryId] = useState(null);
    const [editingContent, setEditingContent] = useState('');
    const [deletingMemoryId, setDeletingMemoryId] = useState(null);

    useEffect(() => {
        loadSettings();
    }, []);

    useEffect(() => {
        if (activeTab === 'memory') {
            loadMemories();
            loadMemorySettings();
        }
    }, [activeTab]);

    const loadSettings = async () => {
        try {
            const data = await apiService.get('/settings');
            setSettings(data);
        } catch (err) {
            logger.error('Failed to load settings:', err);
        }
    };

    const loadMemories = async () => {
        setMemoriesLoading(true);
        try {
            const data = await memoryService.getMemories();
            setMemories(data);
        } catch (err) {
            logger.error('Failed to load memories:', err);
        } finally {
            setMemoriesLoading(false);
        }
    };

    const loadMemorySettings = async () => {
        try {
            const data = await memoryService.getMemorySettings();
            setMemoryEnabled(data.enabled);
        } catch (err) {
            logger.error('Failed to load memory settings:', err);
        }
    };

    const handleToggleMemory = async (enabled) => {
        setMemoryEnabled(enabled);
        try {
            await memoryService.updateMemorySettings({ enabled });
        } catch (err) {
            logger.error('Failed to update memory settings:', err);
            setMemoryEnabled(!enabled);
        }
    };

    const handleStartEdit = (memory) => {
        setEditingMemoryId(memory.id);
        setEditingContent(memory.content);
    };

    const handleCancelEdit = () => {
        setEditingMemoryId(null);
        setEditingContent('');
    };

    const handleSaveMemory = async (memoryId) => {
        try {
            await memoryService.updateMemory(memoryId, editingContent);
            setMemories((prev) =>
                prev.map((m) => (m.id === memoryId ? { ...m, content: editingContent } : m))
            );
            setEditingMemoryId(null);
            setEditingContent('');
        } catch (err) {
            logger.error('Failed to update memory:', err);
        }
    };

    const handleDeleteMemory = async (memoryId) => {
        setDeletingMemoryId(memoryId);
    };

    const confirmDeleteMemory = async () => {
        if (!deletingMemoryId) return;
        try {
            await memoryService.deleteMemory(deletingMemoryId);
            setMemories((prev) => prev.filter((m) => m.id !== deletingMemoryId));
        } catch (err) {
            logger.error('Failed to delete memory:', err);
        } finally {
            setDeletingMemoryId(null);
        }
    };

    const handleSave = async () => {
        try {
            await apiService.put('/settings', settings);
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (err) {
            logger.error('Failed to save settings:', err);
        }
    };

    return (
        <div className="h-full overflow-y-auto">
            <div className="max-w-4xl mx-auto px-6 py-8">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
                    <p className="text-sm text-text-secondary mt-1">Manage your account and application preferences</p>
                </div>

                <div className="flex gap-8">
                    {/* Tabs sidebar */}
                    <nav className="w-48 shrink-0">
                        <ul className="space-y-1">
                            {TABS.map((tab) => (
                                <li key={tab.id}>
                                    <button
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === tab.id
                                                ? 'bg-primary/10 text-primary font-medium'
                                                : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                                            }`}
                                    >
                                        <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d={tab.icon} />
                                        </svg>
                                        <span>{tab.label}</span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </nav>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        {activeTab === 'general' && (
                            <div className="space-y-8">
                                <Section title="Communication Mode" desc="Choose how the app communicates with the AI backend.">
                                    <ModeSelector
                                        mode={settings.communication_mode}
                                        onChange={(mode) => setSettings({ ...settings, communication_mode: mode })}
                                    />
                                    <p className="text-xs text-text-muted mt-2">
                                        Streaming: SSE-based (default) &bull; WebSocket: Real-time bidirectional
                                    </p>
                                </Section>

                                <Section title="Show Timestamps" desc="Display timestamps on chat messages.">
                                    <Toggle
                                        checked={settings.show_timestamps}
                                        onChange={(val) => setSettings({ ...settings, show_timestamps: val })}
                                    />
                                </Section>

                                <Section title="Welcome Message" desc="Customize the initial greeting message shown in new conversations.">
                                    <div className="prose prose-sm max-w-none border border-border rounded-lg overflow-hidden">
                                        <SimpleMDE
                                            value={settings.welcome_message || ''}
                                            onChange={(value) => setSettings({ ...settings, welcome_message: value })}
                                            options={{
                                                spellChecker: false,
                                                maxHeight: '150px',
                                                status: false,
                                                toolbar: ['bold', 'italic', 'heading', '|', 'quote', 'code', 'unordered-list', 'ordered-list', '|', 'preview', 'guide'],
                                            }}
                                        />
                                    </div>
                                </Section>
                            </div>
                        )}

                        {activeTab === 'memory' && (
                            <div className="space-y-8">
                                <Section title="Memory Collection" desc="When enabled, the AI will learn and remember facts about you from conversations.">
                                    <div className="flex items-center justify-between bg-bg-secondary rounded-lg p-4 border border-border">
                                        <div>
                                            <p className="text-sm font-medium text-text-primary">
                                                {memoryEnabled ? 'Memory is active' : 'Memory is paused'}
                                            </p>
                                            <p className="text-xs text-text-muted mt-0.5">
                                                {memoryEnabled
                                                    ? 'The AI collects personal facts from conversations to personalize responses.'
                                                    : 'The AI will not collect new facts from conversations.'}
                                            </p>
                                        </div>
                                        <Toggle checked={memoryEnabled} onChange={handleToggleMemory} />
                                    </div>
                                </Section>

                                <Section
                                    title="Stored Memories"
                                    desc={`The AI has learned ${memories.length} fact${memories.length !== 1 ? 's' : ''} about you. You can edit or delete any of them.`}
                                >
                                    {memoriesLoading ? (
                                        <div className="text-center py-8 text-text-muted text-sm">Loading memories...</div>
                                    ) : memories.length === 0 ? (
                                        <div className="text-center py-8 border border-dashed border-border rounded-lg">
                                            <svg className="mx-auto w-10 h-10 text-text-muted mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                            </svg>
                                            <p className="text-sm text-text-muted">No memories yet</p>
                                            <p className="text-xs text-text-muted mt-1">Start chatting and the AI will learn about you.</p>
                                        </div>
                                    ) : (
                                        <div className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
                                            {memories.map((memory) => (
                                                <div
                                                    key={memory.id}
                                                    className="group bg-white border border-border rounded-lg p-3 hover:border-primary/30 transition-colors"
                                                >
                                                    {editingMemoryId === memory.id ? (
                                                        <div className="space-y-2">
                                                            <textarea
                                                                value={editingContent}
                                                                onChange={(e) => setEditingContent(e.target.value)}
                                                                rows={2}
                                                                className="w-full text-sm bg-bg-secondary text-text-primary border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-none"
                                                                autoFocus
                                                            />
                                                            <div className="flex justify-end gap-2">
                                                                <button
                                                                    onClick={handleCancelEdit}
                                                                    className="px-3 py-1 text-xs text-text-secondary bg-white border border-border rounded-md hover:bg-bg-tertiary transition-colors"
                                                                >
                                                                    Cancel
                                                                </button>
                                                                <button
                                                                    onClick={() => handleSaveMemory(memory.id)}
                                                                    className="px-3 py-1 text-xs text-white bg-primary rounded-md hover:bg-primary-dark transition-colors"
                                                                >
                                                                    Save
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <div className="flex items-start justify-between gap-3">
                                                            <p className="text-sm text-text-primary flex-1 leading-relaxed">{memory.content}</p>
                                                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                                                <button
                                                                    onClick={() => handleStartEdit(memory)}
                                                                    className="p-1.5 text-text-muted hover:text-primary hover:bg-primary/5 rounded-md transition-colors"
                                                                    title="Edit"
                                                                >
                                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                                                    </svg>
                                                                </button>
                                                                <button
                                                                    onClick={() => handleDeleteMemory(memory.id)}
                                                                    className="p-1.5 text-text-muted hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                                                                    title="Delete"
                                                                >
                                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                                    </svg>
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </Section>
                            </div>
                        )}

                        {/* Delete memory confirmation modal */}
                        {deletingMemoryId && (
                            <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
                                <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl border border-border">
                                    <div className="flex items-center space-x-3 mb-4 text-red-600">
                                        <div className="p-2 bg-red-100 rounded-full">
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </div>
                                        <h3 className="text-base font-semibold text-gray-900">Delete Memory</h3>
                                    </div>
                                    <p className="text-sm text-text-secondary mb-5">
                                        Are you sure you want to delete this memory? The AI will no longer remember this fact about you.
                                    </p>
                                    <div className="flex space-x-3">
                                        <button
                                            onClick={() => setDeletingMemoryId(null)}
                                            className="flex-1 px-4 py-2 bg-white border border-border text-text-secondary hover:bg-bg-secondary rounded-lg transition-colors font-medium text-sm"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={confirmDeleteMemory}
                                            className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium shadow-sm text-sm"
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'profile' && (
                            <div className="space-y-8">
                                <Section title="Account Information" desc="Your personal details.">
                                    <div className="flex items-center space-x-4 mb-6">
                                        <div className="w-16 h-16 rounded-full bg-primary flex items-center justify-center text-white text-xl font-bold">
                                            {user?.fullName?.charAt(0).toUpperCase() || 'U'}
                                        </div>
                                        <div>
                                            <p className="text-lg font-semibold text-text-primary">{user?.fullName || 'User'}</p>
                                            <p className="text-sm text-text-secondary">{user?.email || ''}</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 gap-4">
                                        <Field label="Full Name" value={user?.fullName || ''} readOnly />
                                        <Field label="Email" value={user?.email || ''} readOnly />
                                    </div>
                                </Section>
                            </div>
                        )}

                        {activeTab === 'appearance' && (
                            <div className="space-y-8">
                                <Section title="Theme" desc="Choose the visual theme for the application.">
                                    <select
                                        value={settings.theme}
                                        onChange={(e) => setSettings({ ...settings, theme: e.target.value })}
                                        className="w-full max-w-xs bg-bg-secondary text-text-primary border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                                    >
                                        <option value="light-green">Light Green (Default)</option>
                                        <option value="dark">Dark (Coming Soon)</option>
                                    </select>
                                </Section>
                            </div>
                        )}

                        {activeTab === 'connection' && (
                            <div className="space-y-8">
                                <Section title="Connection Status" desc="Current connection state to the backend server.">
                                    <div className="bg-bg-secondary rounded-lg p-4 border border-border">
                                        <ConnectionStatus status="connected" />
                                    </div>
                                </Section>
                            </div>
                        )}

                        {/* Save button */}
                        <div className="mt-10 pt-6 border-t border-border flex items-center justify-end space-x-3">
                            {saved && (
                                <span className="text-sm text-green-600 font-medium animate-fade-in">
                                    Settings saved!
                                </span>
                            )}
                            <button
                                onClick={handleSave}
                                className="px-6 py-2.5 bg-primary hover:bg-primary-dark text-white rounded-lg transition-colors font-medium shadow-sm hover:shadow-md"
                            >
                                Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* ---- Small helper components ---- */

function Section({ title, desc, children }) {
    return (
        <div>
            <h3 className="text-base font-semibold text-text-primary">{title}</h3>
            {desc && <p className="text-sm text-text-secondary mt-0.5 mb-4">{desc}</p>}
            {children}
        </div>
    );
}

function Toggle({ checked, onChange }) {
    return (
        <label className="relative inline-flex items-center cursor-pointer">
            <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onChange(e.target.checked)}
                className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
        </label>
    );
}

function Field({ label, value, readOnly }) {
    return (
        <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">{label}</label>
            <input
                type="text"
                value={value}
                readOnly={readOnly}
                className="w-full bg-bg-secondary text-text-primary border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all read-only:cursor-default read-only:opacity-70"
            />
        </div>
    );
}
