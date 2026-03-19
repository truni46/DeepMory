export default function ConversationList({ conversations = [], activeId, onSelect, onDelete, deletingId }) {
    return (
        <div className="px-2 space-y-1 overflow-y-auto custom-scrollbar">
            {conversations.map((conv) => (
                <div
                    key={conv.id}
                    className={`group relative flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-all duration-300 ease-in-out ${activeId === conv.id
                        ? 'bg-bg-tertiary'
                        : 'hover:bg-bg-tertiary'
                        } ${deletingId === conv.id ? 'opacity-0 -translate-x-full h-0 mb-0 py-0 overflow-hidden' : ''}`}
                    onClick={() => onSelect(conv.id)}
                >
                    <div className="flex items-center space-x-2 flex-1 min-w-0">
                        <svg className="w-4 h-4 text-text-secondary flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                        <span 
                            className="text-sm md:text-[13px] text-text-primary truncate"
                            title={conv.title || 'New conversation'}
                        >
                            {conv.title || 'New conversation'}
                        </span>
                    </div>

                    {/* Delete button - show on hover */}
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onDelete(conv.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-page rounded transition-opacity flex-shrink-0"
                        title="Delete conversation"
                    >
                        <svg className="w-4 h-4 text-text-secondary hover:text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </div>
            ))}

            {conversations.length === 0 && (
                <div className="text-center py-8 text-text-muted text-sm md:text-[13px]">
                    No conversations yet
                </div>
            )}
        </div>
    );
}
