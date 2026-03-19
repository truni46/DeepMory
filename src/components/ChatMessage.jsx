import ReactMarkdown from 'react-markdown';

export default function ChatMessage({ message, showTimestamp = true }) {
    const isUser = message.role === 'user';
    const timestamp = new Date(message.createdAt || message.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6 group w-full`}>
            <div className={`flex items-start space-x-3 ${isUser ? 'max-w-[75%]' : 'w-full'}`}>
                {/* Message Content */}
                <div className="flex flex-col space-y-1 w-full">
                    <div className={`${isUser ? 'bg-primary text-white' : 'bg-transparent w-full'} rounded-xl px-4 py-3`}>
                        <div className={`prose prose-sm max-w-none break-words ${isUser ? 'text-white prose-invert' : 'text-text-primary'} [&>p]:!text-[14.5px] [&>p]:!leading-loose [&>ul>li]:!text-[14.5px] [&>ul>li]:!leading-loose [&>ol>li]:!text-[14.5px] [&>ol>li]:!leading-loose [&>ul]:!list-disc [&>ul]:!pl-5`}>
                            {isUser ? (
                                <p className="whitespace-pre-wrap !text-[14.5px] !leading-loose">{message.content}</p>
                            ) : (
                                <ReactMarkdown
                                    components={{
                                        code({ node, inline, className, children, ...props }) {
                                            const match = /language-(\w+)/.exec(className || '')
                                            return !inline && match ? (
                                                <div className="rounded-md bg-gray-800 p-2 my-2 overflow-x-auto text-xs text-white">
                                                    <code className={className} {...props}>
                                                        {children}
                                                    </code>
                                                </div>
                                            ) : (
                                                <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono text-red-500" {...props}>
                                                    {children}
                                                </code>
                                            )
                                        }
                                    }}
                                >
                                    {message.content}
                                </ReactMarkdown>
                            )}
                        </div>
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
