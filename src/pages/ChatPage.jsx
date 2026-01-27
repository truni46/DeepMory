
import { useState, useEffect, useRef } from 'react';
import { FiLogOut } from 'react-icons/fi';
import Sidebar from '../components/Sidebar';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TypingIndicator from '../components/TypingIndicator';
import SettingsPanel from '../components/SettingsPanel';
import conversationService from '../services/conversationService';
import streamingService from '../services/streamingService';
import websocketService from '../services/websocketService';
import apiService from '../services/apiService';
import logger from '../utils/logger';
import { useAuth } from '../context/AuthContext';

export default function ChatPage() {
    // State
    const [conversations, setConversations] = useState([]);
    const [activeConversationId, setActiveConversationId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    const [initialLoad, setInitialLoad] = useState(true);
    const [settings, setSettings] = useState({
        communication_mode: 'streaming',
        show_timestamps: true,
        theme: 'light-green'
    });
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [showSettings, setShowSettings] = useState(false);
    const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
    const [streamingMessage, setStreamingMessage] = useState('');

    // Auth context
    const { user, logout } = useAuth();

    const messagesEndRef = useRef(null);

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, streamingMessage]);

    // Load initial data
    useEffect(() => {
        const initApp = async () => {
            await loadConversations();
            await loadSettings();
            setInitialLoad(false);
        };
        initApp();
    }, []);

    // Handle settings changes
    useEffect(() => {
        if (settings.communication_mode === 'websocket') {
            connectWebSocket();
        } else {
            disconnectWebSocket();
        }
        return () => disconnectWebSocket();
    }, [settings.communication_mode]);

    // Load conversations
    const loadConversations = async () => {
        try {
            const convs = await conversationService.getAllConversations();
            setConversations(convs);
            if (convs.length > 0 && !activeConversationId) {
                setActiveConversationId(convs[0].id);
                loadMessages(convs[0].id);
            }
        } catch (error) {
            logger.error('Error loading conversations:', error);
        }
    };

    // Load messages
    const loadMessages = async (conversationId) => {
        try {
            const msgs = await conversationService.getChatHistory(conversationId);
            setMessages(msgs);
        } catch (error) {
            logger.error('Error loading messages:', error);
        }
    };

    // Load settings
    const loadSettings = async () => {
        try {
            const settingsData = await apiService.get('/settings');
            setSettings(settingsData);
        } catch (error) {
            logger.error('Error loading settings:', error);
        }
    };

    // WebSocket methods
    const connectWebSocket = () => {
        setConnectionStatus('connecting');
        websocketService.connect(
            () => setConnectionStatus('connected'),
            () => setConnectionStatus('disconnected'),
            (error) => logger.error('WebSocket error:', error)
        );

        websocketService.onMessageChunk((data) => {
            setStreamingMessage(prev => prev + data.chunk);
        });

        websocketService.onMessageComplete((data) => {
            const newMessage = {
                role: 'assistant',
                content: data.fullResponse,
                created_at: new Date().toISOString()
            };
            setMessages(prev => [...prev, newMessage]);
            setStreamingMessage('');
            setIsTyping(false);
        });

        websocketService.onTyping((data) => {
            setIsTyping(data.isTyping);
        });

        websocketService.onError((error) => {
            logger.error('WebSocket message error:', error);
            setIsTyping(false);
        });
    };

    const disconnectWebSocket = () => {
        websocketService.disconnect();
        setConnectionStatus('disconnected');
    };

    // Chat Actions
    const handleNewChat = async () => {
        try {
            const newConv = await conversationService.createConversation();
            setConversations(prev => [newConv, ...prev]);
            setActiveConversationId(newConv.id);
            setMessages([]);
        } catch (error) {
            logger.error('Error creating chat:', error);
        }
    };

    const handleSelectConversation = async (id) => {
        setActiveConversationId(id);
        await loadMessages(id);
    };

    const handleDeleteConversation = async (id) => {
        if (!confirm('Delete conversation?')) return;
        try {
            await conversationService.deleteConversation(id);
            setConversations(prev => prev.filter(c => c.id !== id));
            if (activeConversationId === id) {
                const remaining = conversations.filter(c => c.id !== id);
                if (remaining.length > 0) {
                    handleSelectConversation(remaining[0].id);
                } else {
                    setActiveConversationId(null);
                    setMessages([]);
                }
            }
        } catch (error) {
            logger.error('Error deleting chat:', error);
        }
    };

    const handleSendMessage = async (messageText) => {
        if (!activeConversationId) {
            await handleNewChat();
        }

        const userMessage = {
            role: 'user',
            content: messageText,
            created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMessage]);
        setIsTyping(true);

        try {
            if (settings.communication_mode === 'websocket') {
                websocketService.sendMessageStreaming(messageText, activeConversationId);
            } else {
                setStreamingMessage('');
                await streamingService.sendMessage(
                    messageText,
                    activeConversationId,
                    (chunk) => setStreamingMessage(prev => prev + chunk),
                    (fullResponse) => {
                        const aiMessage = {
                            role: 'assistant',
                            content: fullResponse,
                            created_at: new Date().toISOString()
                        };
                        setMessages(prev => [...prev, aiMessage]);
                        setStreamingMessage('');
                        setIsTyping(false);

                        if (messages.length === 0) {
                            updateConversationTitle(activeConversationId, messageText);
                        }
                    },
                    (error) => {
                        logger.error('Stream error:', error);
                        setIsTyping(false);
                        setStreamingMessage('');
                    }
                );
            }
        } catch (error) {
            console.error(error);
            setIsTyping(false);
        }
    };

    const updateConversationTitle = async (id, text) => {
        const title = text.length > 50 ? text.substring(0, 50) + '...' : text;
        await conversationService.updateConversation(id, { title });
        loadConversations();
    };

    const handleSaveSettings = async (newSettings) => {
        try {
            await apiService.put('/settings', newSettings);
            setSettings(newSettings);
        } catch (error) {
            logger.error('Error saving settings:', error);
        }
    };

    // Render
    if (initialLoad) {
        return (
            <div className="flex h-screen items-center justify-center bg-bg-main">
                <div className="text-center">
                    <div className="text-6xl mb-4 animate-bounce">🤖</div>
                    <h2 className="text-xl font-semibold text-primary">Loading AI Tutor...</h2>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen bg-bg-main text-text-primary">
            <Sidebar
                conversations={conversations}
                activeConversationId={activeConversationId}
                onNewChat={handleNewChat}
                onSelectConversation={handleSelectConversation}
                onDeleteConversation={handleDeleteConversation}
                onOpenSettings={() => setShowSettings(true)}
                user={user}
            />

            <div className="flex-1 flex flex-col">
                <div className="bg-white border-b border-border px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <button className="p-2 hover:bg-bg-secondary rounded-lg">
                            <svg className="w-5 h-5 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                            </svg>
                        </button>
                        <h2 className="text-sm font-medium text-text-primary">
                            {activeConversationId
                                ? conversations.find(c => c.id === activeConversationId)?.title || 'Chat'
                                : 'New Conversation'
                            }
                        </h2>
                    </div>

                    <div className="flex items-center space-x-2">
                        <button
                            onClick={() => setShowLogoutConfirm(true)}
                            className="bg-red-50 text-red-600 px-3 py-1.5 rounded-lg text-sm hover:bg-red-100 transition-colors flex items-center gap-2"
                        >
                            <FiLogOut className="w-4 h-4" />
                            <span>Logout</span>
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6">
                    {messages.length === 0 && !isTyping ? (
                        <div className="h-full flex flex-col items-center justify-center text-center px-4">
                            <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center text-white font-bold text-lg mb-3">
                                AI
                            </div>
                            <h3 className="text-lg font-semibold text-text-primary mb-1">How can I help you today?</h3>
                            <p className="text-sm text-text-secondary max-w-md">
                                Start a conversation by typing a message below.
                            </p>
                        </div>
                    ) : (
                        <div className="max-w-3xl mx-auto pb-4">
                            {messages.map((msg, index) => (
                                <ChatMessage
                                    key={index}
                                    message={msg}
                                    showTimestamp={settings.show_timestamps}
                                />
                            ))}
                            {isTyping && !streamingMessage && <TypingIndicator />}
                            {streamingMessage && (
                                <ChatMessage
                                    message={{
                                        role: 'assistant',
                                        content: streamingMessage,
                                        created_at: new Date().toISOString()
                                    }}
                                    showTimestamp={false}
                                />
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    )}
                </div>

                <ChatInput onSend={handleSendMessage} disabled={isTyping} />
            </div>

            <SettingsPanel
                isOpen={showSettings}
                onClose={() => setShowSettings(false)}
                settings={settings}
                onSave={handleSaveSettings}
                connectionStatus={connectionStatus}
            />

            {/* Logout Confirmation Modal */}
            {showLogoutConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
                    <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl border border-border">
                        <div className="flex items-center space-x-3 mb-4 text-red-600">
                            <div className="p-2 bg-red-100 rounded-full">
                                <FiLogOut className="w-6 h-6" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900">Confirm Logout</h3>
                        </div>
                        <p className="text-text-secondary mb-6">
                            Are you sure you want to log out? You will need to sign in again to access your conversations.
                        </p>
                        <div className="flex space-x-3">
                            <button
                                onClick={() => setShowLogoutConfirm(false)}
                                className="flex-1 px-4 py-2 bg-white border border-border text-text-secondary hover:bg-bg-secondary rounded-lg transition-colors font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={logout}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium shadow-sm"
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
