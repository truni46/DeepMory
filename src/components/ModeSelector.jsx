export default function ModeSelector({ mode, onChange }) {
    return (
        <div className="flex items-center space-x-2 bg-deep-forest bg-opacity-50 rounded-lg p-1">
            <button
                onClick={() => onChange('streaming')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${mode === 'streaming'
                        ? 'bg-bright-green text-white'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
            >
                <span className="mr-1">🔄</span>
                Streaming
            </button>

            <button
                onClick={() => onChange('websocket')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${mode === 'websocket'
                        ? 'bg-bright-green text-white'
                        : 'text-gray-400 hover:text-gray-200'
                    }`}
            >
                <span className="mr-1">⚡</span>
                WebSocket
            </button>
        </div>
    );
}
