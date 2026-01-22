export default function TypingIndicator() {
    return (
        <div className="flex items-center space-x-2 px-4 py-3 bg-ai-msg rounded-2xl max-w-[80px]">
            <div className="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
            <div className="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
            <div className="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
        </div>
    );
}
