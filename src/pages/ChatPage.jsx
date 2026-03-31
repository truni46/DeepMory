import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useOutletContext } from 'react-router-dom';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TypingIndicator from '../components/TypingIndicator';
import AgentTaskList from '../components/ui/AgentTaskList';
import conversationService from '../services/conversationService';
import streamingService from '../services/streamingService';
import agentStreamService from '../services/agentStreamService';
import websocketService from '../services/websocketService';
import logger from '../utils/logger';

const AGENT_STEPS = [
    { id: 'research',  label: 'Researching' },
    { id: 'planner',   label: 'Planning' },
    { id: 'implement', label: 'Implementing' },
    { id: 'testing',   label: 'Testing' },
    { id: 'report',    label: 'Generating report' },
];

export default function ChatPage() {
    const { activeConversationId, setActiveConversationId, settings, loadConversations } = useOutletContext();

    const [messages, setMessages] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [streamingMessage, setStreamingMessage] = useState('');
    const [agentGroups, setAgentGroups] = useState(null);
    const [calledAgent, setCalledAgent] = useState('');

    const messagesEndRef = useRef(null);
    const justCreatedConversationId = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, streamingMessage, agentGroups]);

    useEffect(() => {
        return () => agentStreamService.cancel();
    }, []);

    useEffect(() => {
        if (settings.communication_mode === 'websocket') {
            connectWebSocket();
        } else {
            disconnectWebSocket();
        }
        return () => disconnectWebSocket();
    }, [settings.communication_mode]);

    useEffect(() => {
        if (activeConversationId) {
            if (activeConversationId === justCreatedConversationId.current) {
                justCreatedConversationId.current = null;
            } else {
                loadMessages(activeConversationId);
            }
        } else {
            setMessages([]);
        }
    }, [activeConversationId]);

    useEffect(() => {
        if (!agentGroups || agentGroups.length === 0) return;

        let hasChanges = false;
        const newGroups = agentGroups.map(group => {
            const steps = [...group.steps];
            const procIdx = steps.findIndex(s => s.status === 'processing');
            
            if (procIdx !== -1) {
                hasChanges = true;
                steps[procIdx] = { ...steps[procIdx], status: 'completed' };
                const nextPendIdx = steps.findIndex(s => s.status === 'pending');
                if (nextPendIdx !== -1) {
                    steps[nextPendIdx] = { ...steps[nextPendIdx], status: 'processing' };
                }
            } else {
                const pendIdx = steps.findIndex(s => s.status === 'pending');
                if (pendIdx !== -1) {
                    hasChanges = true;
                    steps[pendIdx] = { ...steps[pendIdx], status: 'processing' };
                }
            }
            
            return { ...group, steps };
        });

        if (hasChanges) {
            const timer = setTimeout(() => {
                setAgentGroups(newGroups);
            }, 600);
            return () => clearTimeout(timer);
        }
    }, [agentGroups]);

    const loadMessages = async (conversationId) => {
        try {
            const msgs = await conversationService.getChatHistory(conversationId);
            setMessages(msgs);
        } catch (error) {
            logger.error('Error loading messages:', error);
        }
    };

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
                createdAt: new Date().toISOString()
            };
            setMessages(prev => [...prev, newMessage]);
            setStreamingMessage('');
            setIsTyping(false);
            scrollToBottom();

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

    const handleAgentTask = async (taskId, conversationId) => {
        setAgentGroups([]);

        try {
            await agentStreamService.streamTask(
                taskId,
                (event) => {
                    const skipNodes = ['supervisor', '__start__', '__end__'];
                    if (skipNodes.includes(event.agentType)) return;

                    setAgentGroups(prev => {
                        let groups = prev ? [...prev] : [];

                        let tasks = [];
                        if (event.output?.plan?.steps) {
                            tasks = event.output.plan.steps.map((st, idx) => ({
                                id: `step_${idx}`,
                                label: typeof st.description === 'string' ? st.description : (st.name || 'Task step'),
                                status: 'pending'
                            }));
                        } else {
                            const content = typeof event.output?.content === 'string' ? event.output.content : '';
                            const bullets = content.split('\n').filter(line => line.trim().startsWith('- '));
                            if (bullets.length > 0) {
                                tasks = bullets.slice(0, 5).map((b, idx) => ({
                                    id: `step_${idx}`,
                                    label: b.replace('- ', '').replace('*', '').trim().substring(0, 80),
                                    status: 'pending'
                                }));
                            } else {
                                tasks = [{ id: '1', label: `Executed task in background`, status: 'completed' }, 
                                         { id: '2', label: `Executed task in background`, status: 'pending' }, 
                                         { id: '3', label: `Executed task in background`, status: 'pending' }];
                            }
                        }

                        const agentNameMap = {
                            research: 'Research Agent',
                            planner: 'Planning Agent',
                            implement: 'Implementation Agent',
                            testing: 'Testing Agent',
                            report: 'Reporting Agent'
                        };
                        const agentName = agentNameMap[event.agentType] || event.agentType;

                        groups.push({
                            id: event.agentType + '_' + Date.now(),
                            agentName: agentName,
                            steps: tasks
                        });

                        return groups;
                    });
                },
                (event) => {
                    setAgentGroups(prev => 
                        prev ? prev.map(g => ({
                            ...g,
                            steps: g.steps.map(s => ({ ...s, status: 'completed' }))
                        })) : prev
                    );

                    if (event.finalReport) {
                        const aiMessage = {
                            role: 'assistant',
                            content: event.finalReport,
                            createdAt: new Date().toISOString(),
                        };
                        setMessages(prev => [...prev, aiMessage]);
                    }

                    setIsTyping(false);

                    if (conversationId) {
                        setTimeout(() => loadConversations(), 2500);
                    }
                },
                (error) => {
                    logger.error('Agent stream error:', error);
                    setAgentGroups(prev => 
                        prev ? prev.map(g => ({
                            ...g,
                            steps: g.steps.map(s => s.status === 'processing' ? { ...s, status: 'failed' } : s)
                        })) : prev
                    );
                    setIsTyping(false);
                }
            );
        } catch (error) {
            logger.error('Agent stream failed:', error);
            setIsTyping(false);
        }
    };

    const handleSendMessage = async (messageText) => {
        let currentId = activeConversationId;

        if (!currentId) {
            try {
                const title = messageText.split(' ').slice(0, 4).join(' ') || 'New Conversation';
                const newConv = await conversationService.createConversation(title);
                currentId = newConv.id;
                justCreatedConversationId.current = currentId;
                await loadConversations();
                setActiveConversationId(currentId);
            } catch (e) {
                logger.error("Failed to create chat on send", e);
                return;
            }
        }

        const userMessage = {
            role: 'user',
            content: messageText,
            createdAt: new Date().toISOString()
        };
        
        // Extract Agent Name from "/"
        let agentName = 'General Assistant';
        const slashMatch = messageText.match(/^(\/\w+)/);
        if (slashMatch) {
            const cmd = slashMatch[1];
            const nameMap = {
                '/research': 'Research Agent',
                '/plan': 'Planning Agent',
                '/implement': 'Implementation Agent',
                '/report': 'Reporting Agent',
                '/run': 'Auto Pipeline',
                '/browser': 'Browser Agent'
            };
            agentName = nameMap[cmd] || cmd;
        }
        setCalledAgent(agentName);
        setAgentGroups(null);

        setMessages(prev => [...prev, userMessage]);
        setIsTyping(true);

        try {
            setStreamingMessage('');
            await streamingService.sendMessage(
                messageText,
                currentId,
                (chunk) => setStreamingMessage(prev => prev + chunk),
                (fullResponse) => {
                    const aiMessage = {
                        role: 'assistant',
                        content: fullResponse,
                        createdAt: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, aiMessage]);
                    setStreamingMessage('');
                    setIsTyping(false);

                    if (currentId) {
                        setTimeout(() => loadConversations(), 2500);
                    }
                },
                (error) => {
                    logger.error('Stream error:', error);
                    setIsTyping(false);
                    setStreamingMessage('');
                },
                (taskId) => {
                    handleAgentTask(taskId, currentId);
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
        loadConversations();
    };

    return (
        <div className="flex-1 flex flex-col h-full relative">
            <div className="bg-white border-b border-border px-6 py-3 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center space-x-3">
                    <h2 className="text-sm font-medium text-text-primary">
                        {activeConversationId ? 'Chat' : 'New Conversation'}
                    </h2>
                </div>
                <div className="flex items-center space-x-2">
                </div>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6">
                {messages.length === 0 && !isTyping && !agentGroups ? (
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
                        {agentGroups && agentGroups.length > 0 && (
                            <div className="mb-4">
                                {agentGroups.map((group, gIndex) => (
                                    <div key={group.id} className="mb-4 last:mb-0">
                                        <div className="flex items-center space-x-2 text-text-primary text-sm font-medium mb-2 pl-1">
                                            <span>Calling <span className="font-semibold text-primary">{group.agentName}</span>...</span>
                                        </div>
                                        <AgentTaskList steps={group.steps} />
                                    </div>
                                ))}
                            </div>
                        )}
                        {isTyping && !streamingMessage && <TypingIndicator />}
                        {streamingMessage && (
                            <ChatMessage
                                message={{
                                    role: 'assistant',
                                    content: streamingMessage,
                                    createdAt: new Date().toISOString()
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
    );
}
