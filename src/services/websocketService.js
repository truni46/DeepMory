import { io } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || 'http://localhost:3000';

/**
 * WebSocket Service using Socket.IO
 */
class WebSocketService {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    /**
     * Connect to WebSocket server
     */
    connect(onConnect, onDisconnect, onError) {
        if (this.socket) {
            return;
        }

        this.socket = io(SOCKET_URL, {
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
        });

        this.socket.on('connect', () => {
            console.log('WebSocket connected:', this.socket.id);
            this.isConnected = true;
            this.reconnectAttempts = 0;
            if (onConnect) onConnect();
        });

        this.socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            if (onDisconnect) onDisconnect();
        });

        this.socket.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            this.reconnectAttempts++;
            if (onError) onError(error);
        });

        this.socket.on('connected', (data) => {
            console.log('Server welcome:', data);
        });
    }

    /**
     * Send message to server
     * @param {string} message User message
     * @param {string} conversationId Conversation ID
     */
    sendMessage(message, conversationId) {
        if (!this.isConnected) {
            throw new Error('WebSocket not connected');
        }

        this.socket.emit('sendMessage', { message, conversationId });
    }

    /**
     * Send message with streaming response
     * @param {string} message User message
     * @param {string} conversationId Conversation ID
     */
    sendMessageStreaming(message, conversationId) {
        if (!this.isConnected) {
            throw new Error('WebSocket not connected');
        }

        this.socket.emit('sendMessageStreaming', { message, conversationId });
    }

    /**
     * Listen for incoming messages
     * @param {Function} callback Message callback
     */
    onMessage(callback) {
        this.socket.on('receiveMessage', callback);
    }

    /**
     * Listen for streaming chunks
     * @param {Function} callback Chunk callback
     */
    onMessageChunk(callback) {
        this.socket.on('messageChunk', callback);
    }

    /**
     * Listen for streaming completion
     * @param {Function} callback Completion callback
     */
    onMessageComplete(callback) {
        this.socket.on('messageComplete', callback);
    }

    /**
     * Listen for typing indicator
     * @param {Function} callback Typing callback
     */
    onTyping(callback) {
        this.socket.on('typing', callback);
    }

    /**
     * Listen for errors
     * @param {Function} callback Error callback
     */
    onError(callback) {
        this.socket.on('error', callback);
    }

    /**
     * Send typing indicator
     * @param {boolean} isTyping Whether user is typing
     */
    sendTyping(isTyping) {
        if (this.isConnected) {
            this.socket.emit('typing', { isTyping });
        }
    }

    /**
     * Disconnect from server
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.isConnected = false;
        }
    }

    /**
     * Remove all event listeners
     */
    removeAllListeners() {
        if (this.socket) {
            this.socket.removeAllListeners();
        }
    }
}

export default new WebSocketService();
