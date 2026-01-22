import { useState, useRef, useEffect } from 'react';

export default function ChatInput({ onSend, disabled = false }) {
    const [message, setMessage] = useState('');
    const textareaRef = useRef(null);

    const handleSend = () => {
        if (message.trim() && !disabled) {
            onSend(message.trim());
            setMessage('');
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleInput = (e) => {
        setMessage(e.target.value);

        // Auto-resize textarea
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
    };

    return (
        <div className="border-t border-border bg-white p-4">
            <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end space-x-2 bg-white border border-border rounded-xl shadow-sm p-2">
                    {/* Attach Button */}
                    <button
                        className="flex-shrink-0 p-2 hover:bg-bg-secondary rounded-lg transition-colors"
                        title="Add documents"
                    >
                        <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                    </button>

                    {/* Textarea */}
                    <textarea
                        ref={textareaRef}
                        value={message}
                        onChange={handleInput}
                        onKeyPress={handleKeyPress}
                        placeholder="Ask a question..."
                        disabled={disabled}
                        className="flex-1 bg-transparent text-text-primary placeholder-text-muted resize-none focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-[200px] py-2"
                        rows={1}
                        style={{ minHeight: '24px' }}
                    />

                    {/* Send/Microphone Button */}
                    <button
                        onClick={handleSend}
                        disabled={!message.trim() || disabled}
                        className={`flex-shrink-0 p-2 rounded-lg transition-colors ${message.trim() && !disabled
                                ? 'bg-primary hover:bg-primary-dark text-white'
                                : 'bg-transparent text-text-muted cursor-not-allowed'
                            }`}
                        title={message.trim() ? "Send message" : "Record audio"}
                    >
                        {message.trim() ? (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                        )}
                    </button>
                </div>

                {/* Footer text */}
                <div className="mt-2 text-center text-xs text-text-muted">
                    AI-Tutor can make mistakes, please check the response.
                </div>
            </div>
        </div>
    );
}
