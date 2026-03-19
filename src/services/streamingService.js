const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

/**
 * Server-Sent Events (SSE) Streaming Service
 */
class StreamingService {
    constructor() {
        this.eventSource = null;
    }

    /**
     * Send message and receive streaming response
     * @param {string} message User message
     * @param {string} conversationId Conversation ID
     * @param {Function} onChunk Callback for each chunk
     * @param {Function} onComplete Callback when complete
     * @param {Function} onError Callback on error
     */
    async sendMessage(message, conversationId, onChunk, onComplete, onError) {
        try {
            const token = localStorage.getItem('accessToken');
            const headers = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_BASE_URL}/messages/chat/completions`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ message, conversationId }),
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

                            if (data.error) {
                                onError(new Error(data.error));
                                return;
                            }

                            if (data.chunk) {
                                onChunk(data.chunk);
                            }

                            if (data.done) {
                                onComplete(data.fullResponse);
                                return;
                            }
                        } catch (err) {
                            console.error('Error parsing SSE data:', err);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error);
            onError(error);
        }
    }

    /**
     * Cancel ongoing stream
     */
    cancel() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

export default new StreamingService();
