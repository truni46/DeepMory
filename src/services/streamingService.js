const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';

/**
 * Server-Sent Events (SSE) Streaming Service
 */
class StreamingService {
    constructor() {
        this.eventSource = null;
        this._abortController = null;
    }

    /**
     * Send message and receive streaming response
     * @param {string} message User message
     * @param {string} conversationId Conversation ID
     * @param {Function} onChunk Callback for each chunk
     * @param {Function} onComplete Callback when complete
     * @param {Function} onError Callback on error
     * @param {Function} onAgentTask Callback when agent task is triggered
     * @param {Function} onQuota Callback for quota events (quota object, isExceeded)
     * @param {Array|null} documentIds Document IDs for RAG
     * @param {Function|null} onSources Callback for source citations
     */
    async sendMessage(message, conversationId, onChunk, onComplete, onError, onAgentTask, onQuota, documentIds = null, onSources = null) {
        try {
            this._abortController = new AbortController();

            const token = localStorage.getItem('accessToken');
            const headers = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const payload = { message, conversationId };
            if (documentIds && documentIds.length > 0) {
                payload.documentIds = documentIds;
            }

            const response = await fetch(`${API_BASE_URL}/messages/chat/completions`, {
                method: 'POST',
                headers,
                body: JSON.stringify(payload),
                signal: this._abortController.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.quotaExceeded && onQuota) {
                                onQuota(data.quota, true);
                                return;
                            }

                            if (data.agentTask && onAgentTask) {
                                onAgentTask(data.taskId);
                                return;
                            }

                            if (data.error) {
                                onError(new Error(data.error));
                                return;
                            }

                            if (data.chunk) {
                                onChunk(data.chunk);
                            }

                            if (data.done) {
                                if (data.quota && onQuota) {
                                    onQuota(data.quota, false);
                                }
                                let finalResponse = data.fullResponse || '';
                                if (data.sources && data.sources.length > 0) {
                                    if (onSources) onSources(data.sources);
                                    const seen = new Set();
                                    const unique = data.sources.filter(s => {
                                        if (!s.filename) return false;
                                        const key = `${s.filename}|${s.pageNumber ?? ''}`;
                                        if (seen.has(key)) return false;
                                        seen.add(key);
                                        return true;
                                    });
                                    if (unique.length > 0) {
                                        const lines = unique.map(s => {
                                            const pageAttr = s.pageNumber ? ` page="${s.pageNumber}"` : '';
                                            const label = s.pageNumber ? `${s.filename} (trang ${s.pageNumber})` : s.filename;
                                            return `<docref file="${s.filename}"${pageAttr}>${label}</docref>`;
                                        });
                                        finalResponse += '\n\n---\n**Nguồn tham khảo:**\n' + lines.join('\n');
                                    }
                                }
                                onComplete(finalResponse);
                                return;
                            }
                        } catch (err) {
                            console.error('Error parsing SSE data:', err);
                        }
                    }
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Streaming error:', error);
            }
            onError(error);
        } finally {
            this._abortController = null;
        }
    }

    /**
     * Cancel ongoing stream
     */
    cancel() {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

export default new StreamingService();
