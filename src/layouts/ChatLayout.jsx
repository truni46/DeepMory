import { useState, useEffect, useRef } from 'react';
import { Navigate, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import conversationService from '../services/conversationService';
import apiService from '../services/apiService';
import Sidebar from '../components/Sidebar';
import logger from '../utils/logger';

export default function ChatLayout() {
    const { user, isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    // Lifted State
    const [conversations, setConversations] = useState([]);
    const [activeConversationId, setActiveConversationId] = useState(null);
    const [settings, setSettings] = useState({
        communication_mode: 'streaming',
        show_timestamps: true,
        theme: 'light-green',
        welcome_message: ''
    });

    // Delete Confirmation State
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [itemToDelete, setItemToDelete] = useState(null);
    const [deletingId, setDeletingId] = useState(null); // For animation

    // Load initial data
    useEffect(() => {
        if (isAuthenticated) {
            loadConversations();
            loadSettings();
        }
    }, [isAuthenticated]);

    // Track if we've handled the initial selection
    const hasInitialized = useRef(false);

    // Handle initial active conversation based on nav or list
    useEffect(() => {
        if (!hasInitialized.current && conversations.length > 0 && !activeConversationId && location.pathname === '/') {
            setActiveConversationId(conversations[0].id);
            hasInitialized.current = true;
        }
    }, [conversations, activeConversationId, location.pathname]);

    const loadConversations = async () => {
        try {
            const convs = await conversationService.getAllConversations();
            setConversations(convs);
        } catch (error) {
            logger.error('Error loading conversations:', error);
        }
    };

    const loadSettings = async () => {
        try {
            const settingsData = await apiService.get('/settings');
            setSettings(settingsData);
        } catch (error) {
            logger.error('Error loading settings:', error);
        }
    };

    const handleNewChat = () => {
        setActiveConversationId(null);
        navigate('/');
    };

    const handleSelectConversation = (id) => {
        setActiveConversationId(id);
        navigate('/');
    };

    const handleDeleteRequest = (id) => {
        setItemToDelete(id);
        setShowDeleteConfirm(true);
    };

    const confirmDelete = async () => {
        if (!itemToDelete) return;

        const id = itemToDelete;
        setShowDeleteConfirm(false);
        setDeletingId(id); // Start animation

        // Wait for animation
        setTimeout(async () => {
            // Optimistic update: Remove immediately from UI
            setConversations(prev => prev.filter(c => c.id !== id));
            setDeletingId(null);
            setItemToDelete(null);

            // Handle active selection
            if (activeConversationId === id) {
                const remaining = conversations.filter(c => c.id !== id);
                if (remaining.length > 0) {
                    setActiveConversationId(remaining[0].id);
                } else {
                    setActiveConversationId(null);
                }
            }

            // Perform actual API deletion
            try {
                await conversationService.deleteConversation(id);
            } catch (error) {
                logger.error('Error deleting chat:', error);
                // On error, reload to restore correct state
                loadConversations();
            }
        }, 300); // 300ms match transition duration
    };

    // Legacy method replacement needed for prop compatibility if not updating all
    const handleDeleteConversation = handleDeleteRequest;


    const handleSaveSettings = async (newSettings) => {
        try {
            await apiService.put('/settings', newSettings);
            setSettings(newSettings);
        } catch (error) {
            logger.error('Error saving settings:', error);
        }
    };

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-page">
                <div className="text-center">
                    <div className="text-6xl mb-4 animate-bounce">🤖</div>
                    <h2 className="text-xl font-semibold text-primary">Loading...</h2>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return (
        <div className="flex h-screen bg-white text-text-primary">
            <Sidebar
                conversations={conversations}
                activeConversationId={activeConversationId}
                onNewChat={handleNewChat}
                onSelectConversation={handleSelectConversation}
                onDeleteConversation={handleDeleteConversation}
                user={user}
                deletingId={deletingId}
            />

            <div className="flex-1 flex flex-col h-full overflow-hidden bg-page">
                <Outlet context={{
                    activeConversationId,
                    settings,
                    loadConversations, // Export this so ChatPage can trigger refresh
                    setActiveConversationId
                }} />
            </div>

            {/* Delete Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
                    <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl border border-border">
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete Conversation?</h3>
                        <p className="text-text-secondary mb-6">
                            This action cannot be undone. The conversation will be permanently removed.
                        </p>
                        <div className="flex space-x-3">
                            <button
                                onClick={() => setShowDeleteConfirm(false)}
                                className="flex-1 px-4 py-2 bg-white border border-border text-text-secondary hover:bg-bg-secondary rounded-lg transition-colors font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelete}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium shadow-sm"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
