import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { FiLogOut } from 'react-icons/fi';
import { useOutletContext } from 'react-router-dom';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TypingIndicator from '../components/TypingIndicator';
import conversationService from '../services/conversationService';
import streamingService from '../services/streamingService';
import websocketService from '../services/websocketService';
import logger from '../utils/logger';
import { useAuth } from '../context/AuthContext';

export default function ChatPage() {
    // Context from Layout
    const { activeConversationId, setActiveConversationId, settings, loadConversations } = useOutletContext();
    const { logout } = useAuth();

    // Local State (only chat content)
    const [messages, setMessages] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
    const [streamingMessage, setStreamingMessage] = useState('');

    const messagesEndRef = useRef(null);
    const justCreatedConversationId = useRef(null);

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, streamingMessage]);

    // Cleanup WebSocket
    useEffect(() => {
        if (settings.communication_mode === 'websocket') {
            connectWebSocket();
        } else {
            disconnectWebSocket();
        }
        return () => disconnectWebSocket();
    }, [settings.communication_mode]);

    // Load messages when active conversation changes
    useEffect(() => {
        if (activeConversationId) {
            // If checking a conversation we just created locally, don't fetch from backend (it's empty).
            // Just clear current messages so handleSendMessage's optimistic update can populate it.
            if (activeConversationId === justCreatedConversationId.current) {
                setMessages([]);
                justCreatedConversationId.current = null;
            } else {
                loadMessages(activeConversationId);
            }
        } else {
            setMessages([]);
        }
    }, [activeConversationId]);

    const loadMessages = async (conversationId) => {
        try {
            const msgs = await conversationService.getChatHistory(conversationId);
            setMessages(msgs);
        } catch (error) {
            logger.error('Error loading messages:', error);
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
            scrollToBottom();

            // Refresh to show updated title if needed
            if (activeConversationId) {
                setTimeout(() => loadConversations(), 2500);
            }
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

    const handleSendMessage = async (messageText) => {
        let currentId = activeConversationId;

        // Create conversation if none exists (Lazy Creation)
        if (!currentId) {
            try {
                // Auto-generate title: First 4 words of the message
                const title = messageText.split(' ').slice(0, 4).join(' ') || 'New Conversation';

                const newConv = await conversationService.createConversation(title);
                currentId = newConv.id;
                justCreatedConversationId.current = currentId;

                await loadConversations(); // Refresh layout list
                setActiveConversationId(currentId); // Update layout active ID
            } catch (e) {
                logger.error("Failed to create chat on send", e);
                return;
            }
        }

        const userMessage = {
            role: 'user',
            content: messageText,
            created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMessage]);
        setIsTyping(true);

        try {
            // Force SSE Streaming as per user request
            // if (settings.communication_mode === 'websocket') { ... } 

            setStreamingMessage('');
            await streamingService.sendMessage(
                messageText,
                currentId,
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

                    // Refresh to show updated title if needed
                    if (currentId) {
                        setTimeout(() => loadConversations(), 2500);
                    }
                },
                (error) => {
                    logger.error('Stream error:', error);
                    setIsTyping(false);
                    setStreamingMessage('');
                }
            );
        } catch (error) {
            console.error(error);
            setIsTyping(false);
        }
    };

    const updateConversationTitle = async (id, text) => {
        const title = text.length > 50 ? text.substring(0, 50) + '...' : text;
        await conversationService.updateConversation(id, { title });
        loadConversations(); // Trigger Layout refresh
    };

    return (
        <div className="flex-1 flex flex-col h-full relative">
            {/* Header */}
            <div className="bg-white border-b border-border px-6 py-3 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-3">
                    <h2 className="text-sm font-medium text-text-primary">
                        {activeConversationId ? 'Chat' : 'New Conversation'}
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

            {/* Messages Area */}
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
                        {/* <div className="prose prose-sm text-center max-w-md text-text-primary mt-2">
                            <ReactMarkdown>
                                {settings.welcome_message || "Hello! How can I help you today?\n\nStart a conversation by typing a message below."}
                            </ReactMarkdown>
                        </div> */}
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
