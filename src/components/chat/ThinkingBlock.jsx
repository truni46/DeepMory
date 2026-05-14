import { useState } from 'react';
import { FiChevronRight } from 'react-icons/fi';

function formatDuration(ms) {
    if (ms === null || ms === undefined) return null;
    const totalSec = Math.max(0, Math.round(ms / 1000));
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    if (m > 0) return s > 0 ? `${m}m${s}s` : `${m}m`;
    return `${totalSec}s`;
}

export default function ThinkingBlock({ content, duration }) {
    const [expanded, setExpanded] = useState(false);

    // content===null means this message has no thinking at all — don't render
    if (typeof content !== 'string') return null;

    const isThinking = duration === null || duration === undefined;
    const durationText = formatDuration(duration);
    const hasContent = content.length > 0;

    return (
        <div className="mb-2 select-none">
            <button
                onClick={() => hasContent && !isThinking && setExpanded(e => !e)}
                className={`flex items-center gap-1.5 text-text-secondary transition-colors
                    ${hasContent && !isThinking ? 'hover:text-text-primary cursor-pointer' : 'cursor-default'}`}
            >
                {isThinking ? (
                    <>
                        <span className="inline-block w-3 h-3 border-[1.5px] border-current border-t-transparent rounded-full animate-spin flex-shrink-0" />
                        <span className="text-xs italic opacity-60">Thinking...</span>
                    </>
                ) : (
                    <>
                        <FiChevronRight
                            size={13}
                            className={`flex-shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
                        />
                        <span className="text-xs opacity-60">Thinking in {durationText}</span>
                    </>
                )}
            </button>

            {expanded && hasContent && (
                <div className="mt-2 ml-4 pl-3 border-l-2 border-border text-xs text-text-secondary leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto custom-scrollbar pr-1">
                    {content}
                </div>
            )}
        </div>
    );
}
