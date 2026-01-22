export default function ChatMessage({ message, showTimestamp = true }) {
    const isUser = message.role === 'user';
    const timestamp = new Date(message.created_at || message.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6 group`}>
            <div className={`flex items-start space-x-3 max-w-[75%]`}>
                {/* Avatar */}
                {!isUser && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white font-bold text-sm">
                        AI
                    </div>
                )}

                {/* Message Content */}
                <div className="flex flex-col space-y-1">
                    <div className={`${isUser ? 'bg-user-msg border border-primary border-opacity-20' : 'bg-transparent'} rounded-2xl px-4 py-3`}>
                        <p className={`text-sm leading-relaxed whitespace-pre-wrap break-words ${isUser ? 'text-primary font-medium' : 'text-text-primary'}`}>
                            {message.content}
                        </p>
                    </div>

                    {/* Timestamp - show on hover */}
                    {showTimestamp && (
                        <span className="text-xs text-text-muted opacity-0 group-hover:opacity-100 transition-opacity px-4">
                            {timestamp}
                        </span>
                    )}
                </div>

                {/* User Avatar */}
                {isUser && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-text-secondary font-semibold text-sm">
                        U
                    </div>
                )}
            </div>
        </div>
    );
}
