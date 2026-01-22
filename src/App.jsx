import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatMessage from './components/ChatMessage';
import ChatInput from './components/ChatInput';
import TypingIndicator from './components/TypingIndicator';
import SettingsPanel from './components/SettingsPanel';
import conversationService from './services/conversationService';
import streamingService from './services/streamingService';
import websocketService from './services/websocketService';
import apiService from './services/apiService';
import logger from './utils/logger';

function App() {
    // State
    const [conversations, setConversations] = useState([]);
    const [activeConversationId, setActiveConversationId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [initialLoad, setInitialLoad] = useState(true); // Fix for blank page
    const [settings, setSettings] = useState({
        communication_mode: 'streaming',
        show_timestamps: true,
        theme: 'light-green'
    });
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [showSettings, setShowSettings] = useState(false);
    const [streamingMessage, setStreamingMessage] = useState('');

    const messagesEndRef = useRef(null);

    // Scroll to bottom of messages
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, streamingMessage]);

    // Load conversations on mount
    useEffect(() => {
        const initApp = async () => {
            await loadConversations();
            await loadSettings();
            setInitialLoad(false); // Mark initial load complete
        };
        initApp();
    }, []);

    // Handle communication mode changes
    useEffect(() => {
        if (settings.communication_mode === 'websocket') {
            connectWebSocket();
        } else {
            disconnectWebSocket();
        }

        return () => {
            disconnectWebSocket();
        };
    }, [settings.communication_mode]);

    // Load conversations
    const loadConversations = async () => {
        try {
            console.log('Loading conversations...');
            const convs = await conversationService.getAllConversations();
            console.log('Conversations loaded:', convs);
            setConversations(convs);

            if (convs.length > 0 && !activeConversationId) {
                setActiveConversationId(convs[0].id);
                loadMessages(convs[0].id);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
            logger.error('Error loading conversations:', error);
            // Don't throw - allow app to render even if backend is down
        }
    };

    // Load messages for a conversation
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
            console.log('Loading settings...');
            const settingsData = await apiService.get('/settings');
            console.log('Settings loaded:', settingsData);
            setSettings(settingsData);
        } catch (error) {
            console.error('Error loading settings:', error);
            logger.error('Error loading settings:', error);
            // Use default settings if backend is down
        }
    };

    // Connect WebSocket
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

    // Disconnect WebSocket
    const disconnectWebSocket = () => {
        websocketService.disconnect();
        setConnectionStatus('disconnected');
    };

    // Create new conversation
    const handleNewChat = async () => {
        try {
            const newConv = await conversationService.createConversation();
            setConversations(prev => [newConv, ...prev]);
            setActiveConversationId(newConv.id);
            setMessages([]);
            logger.info('New conversation created:', newConv.id);
        } catch (error) {
            logger.error('Error creating conversation:', error);
        }
    };

    // Select conversation
    const handleSelectConversation = async (id) => {
        setActiveConversationId(id);
        await loadMessages(id);
    };

    // Delete conversation
    const handleDeleteConversation = async (id) => {
        if (!confirm('Delete this conversation?')) return;

        try {
            await conversationService.deleteConversation(id);
            setConversations(prev => prev.filter(c => c.id !== id));

            if (activeConversationId === id) {
                const remaining = conversations.filter(c => c.id !== id);
                if (remaining.length > 0) {
                    setActiveConversationId(remaining[0].id);
                    loadMessages(remaining[0].id);
                } else {
                    setActiveConversationId(null);
                    setMessages([]);
                }
            }
        } catch (error) {
            logger.error('Error deleting conversation:', error);
        }
    };

    // Send message
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
                // WebSocket mode
                websocketService.sendMessageStreaming(messageText, activeConversationId);
            } else {
                // Streaming mode (default)
                setStreamingMessage('');

                await streamingService.sendMessage(
                    messageText,
                    activeConversationId,
                    (chunk) => {
                        setStreamingMessage(prev => prev + chunk);
                    },
                    (fullResponse) => {
                        const aiMessage = {
                            role: 'assistant',
                            content: fullResponse,
                            created_at: new Date().toISOString()
                        };
                        setMessages(prev => [...prev, aiMessage]);
                        setStreamingMessage('');
                        setIsTyping(false);

                        // Update conversation title if first message
                        if (messages.length === 0) {
                            updateConversationTitle(activeConversationId, messageText);
                        }
                    },
                    (error) => {
                        logger.error('Streaming error:', error);
                        setIsTyping(false);
                        setStreamingMessage('');
                    }
                );
            }
        } catch (error) {
            logger.error('Error sending message:', error);
            setIsTyping(false);
        }
    };

    // Update conversation title
    const updateConversationTitle = async (conversationId, firstMessage) => {
        try {
            const title = firstMessage.length > 50 ? firstMessage.substring(0, 50) + '...' : firstMessage;
            await conversationService.updateConversation(conversationId, { title });
            await loadConversations();
        } catch (error) {
            logger.error('Error updating conversation title:', error);
        }
    };

    // Save settings
    const handleSaveSettings = async (newSettings) => {
        try {
            await apiService.put('/settings', newSettings);
            setSettings(newSettings);
            logger.info('Settings saved');
        } catch (error) {
            logger.error('Error saving settings:', error);
        }
    };

    // Show loading screen during initial load
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
            {/* Sidebar */}
            <Sidebar
                conversations={conversations}
                activeConversationId={activeConversationId}
                onNewChat={handleNewChat}
                onSelectConversation={handleSelectConversation}
                onDeleteConversation={handleDeleteConversation}
                onOpenSettings={() => setShowSettings(true)}
            />

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col">
                {/* Header */}
                <div className="bg-white border-b border-border px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        {/* Collapse Sidebar Button */}
                        <button className="p-2 hover:bg-bg-secondary rounded-lg transition-colors">
                            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                            </svg>
                        </button>
                        {/* Title */}
                        <h2 className="text-sm font-medium text-text-primary">
                            {activeConversationId
                                ? conversations.find(c => c.id === activeConversationId)?.title || 'Chat'
                                : 'New Conversation'
                            }
                        </h2>
                    </div>

                    <div className="flex items-center space-x-2">
                        {/* Share Button */}
                        <button className="flex items-center space-x-2 px-3 py-1.5 rounded-lg hover:bg-bg-secondary transition-colors">
                            <svg className="w-4 h-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                            </svg>
                            <span className="text-sm text-text-secondary">Share</span>
                        </button>

                        {/* Upgrade Button */}
                        <button className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-primary-light hover:bg-primary-light text-primary transition-colors">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                            </svg>
                            <span className="text-sm font-medium">Upgrade</span>
                        </button>

                        {/* User Profile */}
                        <button className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-text-secondary font-semibold text-sm hover:bg-gray-400 transition-colors">
                            U
                        </button>
                    </div>
                </div>

                {/* Messages */}
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
                        <div className="max-w-4xl mx-auto">
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

                {/* Input */}
                <ChatInput
                    onSend={handleSendMessage}
                    disabled={isTyping}
                />
            </div>

            {/* Settings Panel */}
            <SettingsPanel
                isOpen={showSettings}
                onClose={() => setShowSettings(false)}
                settings={settings}
                onSave={handleSaveSettings}
                connectionStatus={connectionStatus}
            />
        </div>
    );
}

export default App;
