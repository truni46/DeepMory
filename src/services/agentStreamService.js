const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';

class AgentStreamService {
    constructor() {
        this.abortController = null;
    }

    async startTask(goal, conversationId) {
        const token = localStorage.getItem('accessToken');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const body = { goal };
        if (conversationId) body.conversationId = conversationId;

        const response = await fetch(`${API_BASE_URL}/agents/tasks`, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    async streamTask(taskId, onAgentRun, onDone, onError) {
        try {
            this.abortController = new AbortController();
            const token = localStorage.getItem('accessToken');
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const response = await fetch(`${API_BASE_URL}/agents/tasks/${taskId}/stream`, {
                method: 'GET',
                headers,
                signal: this.abortController.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'agent_run') {
                                onAgentRun(data);
                            } else if (data.type === 'done') {
                                onDone(data);
                                return;
                            } else if (data.type === 'error') {
                                onError(new Error(data.message || 'Agent error'));
                                return;
                            }
                        } catch (err) {
                            console.error('Error parsing agent SSE:', err);
                        }
                    }
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                onError(error);
            }
        }
    }

    cancel() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }
}

export default new AgentStreamService();
