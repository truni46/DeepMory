export default function ChatMessage({ message, showTimestamp = true }) {
    const isUser = message.role === 'user';
    const timestamp = new Date(message.created_at || message.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6 group w-full`}>
            <div className={`flex items-start space-x-3 ${isUser ? 'max-w-[75%]' : 'w-full'}`}>
                {/* Message Content */}
                <div className="flex flex-col space-y-1 w-full">
                    <div className={`${isUser ? 'bg-primary text-white' : 'bg-transparent w-full'} rounded-xl px-4 py-3`}>
                        <p className={`text-sm leading-loose whitespace-pre-wrap break-words ${isUser ? 'text-white font-medium' : 'text-text-primary'}`}>
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
            </div>
        </div>
    );
}
