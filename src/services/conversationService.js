import apiService from './apiService';

/**
 * Conversation Management Service
 */
class ConversationService {
    /**
     * Get all conversations
     */
    async getAllConversations() {
        try {
            return await apiService.get('/conversations');
        } catch (error) {
            console.error('Error fetching conversations:', error);
            throw error;
        }
    }

    /**
     * Create new conversation
     * @param {string} title Conversation title
     */
    async createConversation(title = 'New Chat') {
        try {
            return await apiService.post('/conversations', { title });
        } catch (error) {
            console.error('Error creating conversation:', error);
            throw error;
        }
    }

    /**
     * Get conversation by ID
     * @param {string} id Conversation ID
     */
    async getConversation(id) {
        try {
            return await apiService.get(`/conversations/${id}`);
        } catch (error) {
            console.error('Error fetching conversation:', error);
            throw error;
        }
    }

    /**
     * Update conversation
     * @param {string} id Conversation ID
     * @param {Object} updates Updates to apply
     */
    async updateConversation(id, updates) {
        try {
            return await apiService.patch(`/conversations/${id}`, updates);
        } catch (error) {
            console.error('Error updating conversation:', error);
            throw error;
        }
    }

    /**
     * Delete conversation
     * @param {string} id Conversation ID
     */
    async deleteConversation(id) {
        try {
            return await apiService.delete(`/conversations/${id}`);
        } catch (error) {
            console.error('Error deleting conversation:', error);
            throw error;
        }
    }

    /**
     * Get chat history for conversation
     * @param {string} conversationId Conversation ID
     */
    async getChatHistory(conversationId) {
        try {
            return await apiService.get(`/messages/${conversationId}`);
        } catch (error) {
            console.error('Error fetching chat history:', error);
            throw error;
        }
    }

    /**
     * Export conversation
     * @ param {string} conversationId Conversation ID
     * @param {string} format Export format (json, txt, md)
     */
    async exportConversation(conversationId, format = 'json') {
        try {
            const filename = `conversation-${conversationId}.${format}`;
            await apiService.download(`/export/${conversationId}?format=${format}`, filename);
        } catch (error) {
            console.error('Error exporting conversation:', error);
            throw error;
        }
    }
}

export default new ConversationService();
