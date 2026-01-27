export default function ModeSelector({ mode, onChange }) {
    return (
        <div className="flex items-center space-x-2 bg-bg-secondary border border-border rounded-lg p-1">
            <button
                onClick={() => onChange('streaming')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${mode === 'streaming'
                    ? 'bg-white text-primary shadow-sm ring-1 ring-border'
                    : 'text-text-muted hover:text-text-primary hover:bg-white/50'
                    }`}
            >
                <span className="mr-1">🔄</span>
                Streaming
            </button>

            <button
                onClick={() => onChange('websocket')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${mode === 'websocket'
                    ? 'bg-white text-primary shadow-sm ring-1 ring-border'
                    : 'text-text-muted hover:text-text-primary hover:bg-white/50'
                    }`}
            >
                <span className="mr-1">⚡</span>
                WebSocket
            </button>
        </div>
    );
}
