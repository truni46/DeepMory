import { useState, useEffect, useRef, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useToast } from '../context/ToastContext'; // DEMO - remove after testing
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TypingIndicator from '../components/TypingIndicator';
import AgentTaskList from '../components/AgentTaskList';
import QuotaWidget from '../components/QuotaWidget';
import DocumentSideViewer from '../components/DocumentSideViewer';
import DocumentListPanel from '../components/DocumentListPanel';
import conversationService from '../services/conversationService';
import apiService from '../services/apiService';
import streamingService from '../services/streamingService';
import agentStreamService from '../services/agentStreamService';
import websocketService from '../services/websocketService';
import documentService from '../services/documentService';
import logger from '../utils/logger';

const AGENT_NAME_MAP = {
    research: 'Research Agent',
    planner: 'Planning Agent',
    implement: 'Implementation Agent',
    testing: 'Testing Agent',
    report: 'Reporting Agent',
};

const SCROLL_THRESHOLD = 120; // px from bottom to consider "at bottom"

export default function ChatPage() {
    const { activeConversationId, setActiveConversationId, settings, loadConversations } = useOutletContext();
    const toast = useToast(); // DEMO - remove after testing
    const [messages, setMessages] = useState([]);
    const [isTyping, setIsTyping] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingMessage, setStreamingMessage] = useState('');
    const [agentGroups, setAgentGroups] = useState(null);
    const [quotaStatus, setQuotaStatus] = useState(null);
    const [quotaWarning, setQuotaWarning] = useState(false);
    const [quotaBlocked, setQuotaBlocked] = useState(false);
    const [selectedDocs, setSelectedDocs] = useState([]);
    const [viewingDocument, setViewingDocument] = useState(null);
    const [viewerWidth, setViewerWidth] = useState(400); // pixels

    const splitPaneRef = useRef(null);
    const viewerRef = useRef(null);
    const isResizing = useRef(false);
    const chatScrollRef = useRef(null);
    const userScrolledUp = useRef(false);
    const messagesEndRef = useRef(null);
    const justCreatedConversationId = useRef(null);
    const draftDocsRef = useRef({});
    const prevConvIdRef = useRef(activeConversationId);

    // Resize handlers for the document side viewer
    const startResizing = useCallback(() => {
        isResizing.current = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }, []);

    const stopResizing = useCallback(() => {
        if (isResizing.current) {
            isResizing.current = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            // Sync final DOM width to state (single re-render on release)
            if (viewerRef.current) {
                const finalWidth = parseInt(viewerRef.current.style.width, 10);
                if (!isNaN(finalWidth)) setViewerWidth(finalWidth);
            }
        }
    }, []);

    const resize = useCallback((e) => {
        if (!isResizing.current || !splitPaneRef.current) return;
        const containerRect = splitPaneRef.current.getBoundingClientRect();
        let newWidth = containerRect.right - e.clientX;
        if (newWidth < 200) newWidth = 200;
        if (newWidth > 800) newWidth = 800;
        // Direct DOM update — avoids React re-render on every mousemove
        if (viewerRef.current) {
            viewerRef.current.style.width = `${newWidth}px`;
        }
    }, []);

    useEffect(() => {
        window.addEventListener('mousemove', resize);
        window.addEventListener('mouseup', stopResizing);
        return () => {
            window.removeEventListener('mousemove', resize);
            window.removeEventListener('mouseup', stopResizing);
        };
    }, [resize, stopResizing]);

    // Save/restore doc selection per conversation
    useEffect(() => {
        if (prevConvIdRef.current !== activeConversationId) {
            draftDocsRef.current[prevConvIdRef.current] = selectedDocs;
            setSelectedDocs(draftDocsRef.current[activeConversationId] || []);
            prevConvIdRef.current = activeConversationId;
        }
    }, [activeConversationId, selectedDocs]);

    // Smart scroll: only auto-scroll when user is near the bottom
    const handleChatScroll = useCallback(() => {
        const el = chatScrollRef.current;
        if (!el) return;
        const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        userScrolledUp.current = distanceFromBottom > SCROLL_THRESHOLD;
    }, []);

    const scrollToBottom = useCallback(() => {
        if (!userScrolledUp.current) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping, streamingMessage, agentGroups, scrollToBottom]);

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
        setAgentGroups(null);
        setViewingDocument(null);
    }, [activeConversationId]);

    useEffect(() => {
        const fetchQuota = async () => {
            try {
                const status = await apiService.get(`/quota/status?conversationId=${activeConversationId || ''}`);
                setQuotaStatus(status);
                setQuotaBlocked(!status.allowed);
                setQuotaWarning(status.warning);
            } catch (error) {
                logger.error('Error fetching quota:', error);
            }
        };
        fetchQuota();
    }, [activeConversationId]);

    const loadMessages = async (conversationId) => {
        try {
            const msgs = await conversationService.getChatHistory(conversationId);
            setMessages(msgs);
        } catch (error) {
            logger.error('Error loading messages:', error);
        }
    };

    const connectWebSocket = () => {
        websocketService.connect(
            () => {},
            () => {},
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
    };

    const handleStop = () => {
        streamingService.cancel();
        if (streamingMessage) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: streamingMessage,
                createdAt: new Date().toISOString()
            }]);
        }
        setStreamingMessage('');
        setIsTyping(false);
        setIsStreaming(false);
    };

    const handleAgentTask = async (taskId, conversationId) => {
        setIsStreaming(false);
        setAgentGroups([]);

        const findGroupByAgent = (groups, agentType) => {
            for (let i = groups.length - 1; i >= 0; i--) {
                if (groups[i].agentType === agentType) return i;
            }
            return -1;
        };

        try {
            await agentStreamService.streamTask(
                taskId,
                (event) => {
                    const output = event.output || {};
                    const agentType = event.agentType;

                    if (output.event === 'tasks_generated') {
                        const tasks = (output.tasks || []).map((t, idx) => ({
                            id: `task_${idx}`,
                            label: t.description || `Task ${idx + 1}`,
                            status: 'pending',
                        }));
                        const agentName = AGENT_NAME_MAP[agentType] || agentType;

                        setAgentGroups(prev => [
                            ...(prev || []),
                            { id: `${agentType}_${Date.now()}`, agentType, agentName, steps: tasks },
                        ]);
                    } else if (output.event === 'task_started') {
                        setAgentGroups(prev => {
                            if (!prev) return prev;
                            const groups = [...prev];
                            const gi = findGroupByAgent(groups, agentType);
                            if (gi === -1) return prev;
                            groups[gi] = {
                                ...groups[gi],
                                steps: groups[gi].steps.map((s, idx) =>
                                    idx === output.taskIndex ? { ...s, status: 'processing' } : s
                                ),
                            };
                            return groups;
                        });
                    } else if (output.event === 'task_completed') {
                        setAgentGroups(prev => {
                            if (!prev) return prev;
                            const groups = [...prev];
                            const gi = findGroupByAgent(groups, agentType);
                            if (gi === -1) return prev;
                            groups[gi] = {
                                ...groups[gi],
                                steps: groups[gi].steps.map((s, idx) =>
                                    idx === output.taskIndex ? { ...s, status: 'completed' } : s
                                ),
                            };
                            return groups;
                        });
                    }
                },
                (event) => {
                    setAgentGroups(prev =>
                        prev ? prev.map(g => ({
                            ...g,
                            steps: g.steps.map(s => ({ ...s, status: 'completed' })),
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
                            steps: g.steps.map(s => s.status === 'processing' ? { ...s, status: 'failed' } : s),
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
                const title = 'New Conversation';
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

        setAgentGroups(null);

        setMessages(prev => [...prev, userMessage]);
        setIsTyping(true);
        setIsStreaming(true);

        // Reset scroll position lock so new response scrolls into view
        userScrolledUp.current = false;

        const docIds = selectedDocs.map(d => d.id);

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
                    setIsStreaming(false);
                    // Clear selected docs from input after chat completes
                    setSelectedDocs([]);

                    if (currentId) {
                        setTimeout(() => loadConversations(), 2500);
                    }
                },
                (error) => {
                    if (error.name !== 'AbortError') {
                        logger.error('Stream error:', error);
                        setStreamingMessage('');
                    }
                    setIsTyping(false);
                    setIsStreaming(false);
                },
                (taskId) => {
                    handleAgentTask(taskId, currentId);
                },
                (quota, exceeded) => {
                    setQuotaStatus(quota);
                    setQuotaWarning(quota.warning);
                    setQuotaBlocked(!quota.allowed);
                    if (exceeded) {
                        setIsTyping(false);
                        setIsStreaming(false);
                    }
                },
                docIds.length > 0 ? docIds : null,
                (sources) => {
                    // Sources are attached to the last assistant message after streaming completes
                    // Currently logged; extend here to attach to message metadata if needed
                    logger.info('RAG sources received:', sources);
                },
            );
        } catch (error) {
            logger.error('handleSendMessage error:', error);
            setIsTyping(false);
            setIsStreaming(false);
        }
    };

    const handleCitationClick = async (filename, pageStart, docId, pageEnd = null) => {
        try {
            let docInfo = null;

            if (docId) {
                docInfo = selectedDocs.find(d => d.id === docId);
            }
            if (!docInfo && filename) {
                docInfo = selectedDocs.find(d => d.filename === filename);
            }

            if (!docInfo) {
                const docsResult = await documentService.getDocuments();
                const allDocs = Array.isArray(docsResult) ? docsResult : (docsResult?.data || []);

                if (docId) {
                    docInfo = allDocs.find(d => d.id === docId);
                }
                if (!docInfo && filename) {
                    docInfo = allDocs.find(d => d.filename === filename);
                }
            }

            if (docInfo) {
                setViewingDocument({ doc: docInfo, pageStart, pageEnd });
            } else {
                setViewingDocument({ doc: { filename, id: docId }, pageStart, pageEnd });
            }
        } catch (error) {
            logger.error('Failed to open citation', error);
            setViewingDocument({ doc: { filename, id: docId }, pageStart, pageEnd });
        }
    };

    const handleDocumentsConfirm = (docs) => {
        setSelectedDocs(docs);
    };

    const handleDocumentRemove = (docId) => {
        setSelectedDocs(prev => prev.filter(d => d.id !== docId));
    };

    return (
        <div className="flex flex-col h-full w-full bg-white relative">
            {/* Topbar */}
            <div className="bg-white border-b border-border px-6 py-3 flex items-center justify-between shadow-sm z-20 flex-shrink-0">
                <div className="flex items-center space-x-3">
                    <h2 className="text-sm font-medium text-text-primary">
                        {activeConversationId ? 'Chat' : 'New Conversation'}
                    </h2>
                </div>
                <div className="flex items-center space-x-2">
                    {/* DEMO toast buttons - remove after testing */}
                    <button onClick={() => toast.success('Saved successfully')} className="px-2.5 py-1 bg-green-500 text-white text-xs rounded-md hover:bg-green-600 transition-colors">Toast Success</button>
                    <button onClick={() => toast.info('Request in progress', "We're processing your request. You'll be notified once it's done.")} className="px-2.5 py-1 bg-blue-500 text-white text-xs rounded-md hover:bg-blue-600 transition-colors">Toast Info</button>
                    <button onClick={() => toast.error('Something went wrong', "We couldn't complete your request. Check your connection and try again.")} className="px-2.5 py-1 bg-red-500 text-white text-xs rounded-md hover:bg-red-600 transition-colors">Toast Error</button>
                    {quotaStatus && (
                        <QuotaWidget quota={quotaStatus} warning={quotaWarning} inline />
                    )}
                </div>
            </div>

            {/* Content Area (chat + optional side viewer) */}
            <div className="flex-1 flex w-full relative overflow-hidden bg-page" ref={splitPaneRef}>

                {/* Main Chat Area */}
                <div className="flex flex-col h-full relative flex-1 min-w-0">
                    {/* Floating Document List Panel */}
                    <DocumentListPanel
                        selectedDocs={selectedDocs}
                        onRemove={handleDocumentRemove}
                    />
                    <div
                        ref={chatScrollRef}
                        onScroll={handleChatScroll}
                        className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6"
                    >
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
                                        onDocumentClick={handleCitationClick}
                                    />
                                ))}
                                {agentGroups && agentGroups.length > 0 && (
                                    <div className="mb-6">
                                        {agentGroups.map((group) => (
                                            <AgentTaskList
                                                key={group.id}
                                                steps={group.steps}
                                                agentName={group.agentName}
                                            />
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

                    <ChatInput
                        conversationId={activeConversationId}
                        onSend={handleSendMessage}
                        disabled={isTyping && !isStreaming || quotaBlocked}
                        quotaBlocked={quotaBlocked}
                        quota={quotaStatus}
                        quotaWarning={quotaWarning}
                        selectedDocs={selectedDocs}
                        onDocumentsConfirm={handleDocumentsConfirm}
                        onDocumentRemove={handleDocumentRemove}
                        isStreaming={isStreaming}
                        onStop={handleStop}
                    />
                </div>

                {/* Resizer */}
                {viewingDocument && (
                    <div
                        className="w-1.5 hover:w-2 bg-transparent hover:bg-gray-300 active:bg-blue-400 cursor-col-resize z-50 flex-shrink-0 transition-colors"
                        onMouseDown={startResizing}
                    />
                )}

                {/* Document Side Viewer */}
                {viewingDocument && (
                    <div
                        ref={viewerRef}
                        className="h-full bg-white border-l border-border flex-shrink-0 flex flex-col overflow-hidden"
                        style={{ width: `${viewerWidth}px` }}
                    >
                        <DocumentSideViewer
                            key={`${viewingDocument.doc?.id ?? viewingDocument.doc?.filename}-${viewingDocument.pageStart ?? 'top'}`}
                            document={viewingDocument.doc}
                            pageStart={viewingDocument.pageStart}
                            pageEnd={viewingDocument.pageEnd}
                            onClose={() => setViewingDocument(null)}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
