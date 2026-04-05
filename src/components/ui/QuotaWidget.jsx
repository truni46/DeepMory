import { useState, useRef, useEffect } from 'react';

function formatTokens(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
    return String(n);
}

function formatTime(seconds) {
    if (seconds <= 0) return '0m';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function getColor(percent) {
    if (percent >= 0.9) return { bg: 'bg-red-500', text: 'text-red-600', ring: 'ring-red-400' };
    if (percent >= 0.7) return { bg: 'bg-yellow-500', text: 'text-yellow-600', ring: 'ring-yellow-400' };
    return { bg: 'bg-green-500', text: 'text-green-600', ring: 'ring-green-400' };
}

function ProgressBar({ label, used, limit, percent, extra }) {
    const color = getColor(percent);
    return (
        <div className="mb-3 last:mb-0">
            <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-text-primary">{label}</span>
                <span className={`font-semibold ${color.text}`}>
                    {formatTokens(used)} / {formatTokens(limit)}
                </span>
            </div>
            <div className="w-full h-2 bg-bg-secondary rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${color.bg}`}
                    style={{ width: `${Math.min(percent * 100, 100)}%` }}
                />
            </div>
            {extra && (
                <div className="text-[10px] text-text-muted mt-0.5">{extra}</div>
            )}
        </div>
    );
}

export default function QuotaWidget({ quota, warning }) {
    const [expanded, setExpanded] = useState(false);
    const panelRef = useRef(null);

    useEffect(() => {
        if (warning && quota) setExpanded(true);
    }, [warning]);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (panelRef.current && !panelRef.current.contains(e.target)) {
                setExpanded(false);
            }
        };
        if (expanded) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [expanded]);

    if (!quota) return null;

    const maxPercent = Math.max(quota.session?.percent || 0, quota.weekly?.percent || 0);
    const color = getColor(maxPercent);
    const isBlocked = !quota.allowed;

    return (
        <div className="fixed bottom-24 right-6 z-50" ref={panelRef}>
            {expanded && (
                <div className="mb-2 bg-white border border-border rounded-xl shadow-xl p-4 w-72 animate-in fade-in slide-in-from-bottom-2 duration-200">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-text-primary">Token Usage</h4>
                        {isBlocked && (
                            <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                                QUOTA EXCEEDED
                            </span>
                        )}
                    </div>
                    <ProgressBar
                        label="Session"
                        used={quota.session?.used || 0}
                        limit={quota.session?.limit || 1}
                        percent={quota.session?.percent || 0}
                        extra={`${formatTime(quota.session?.remainingSeconds || 0)} remaining`}
                    />
                    <ProgressBar
                        label="Weekly"
                        used={quota.weekly?.used || 0}
                        limit={quota.weekly?.limit || 1}
                        percent={quota.weekly?.percent || 0}
                        extra={`Resets ${quota.weekly?.resetDay || 'Mon'}`}
                    />
                </div>
            )}

            <button
                onClick={() => setExpanded(!expanded)}
                className={`ml-auto flex items-center justify-center w-10 h-10 rounded-full shadow-lg border-2 border-white transition-all duration-300 ${color.bg} ${warning ? 'animate-pulse' : ''} hover:scale-110`}
                title="Token quota"
            >
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            </button>
        </div>
    );
}
