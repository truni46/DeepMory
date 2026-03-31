import { useRef, useEffect } from 'react';

export default function DropdownMenu({
    items = [],
    selectedIndex = 0,
    onSelect,
    onHover,
    visible = false,
    position = 'top',
    className = '',
    maxHeight = 195,
    renderItem,
}) {
    const listRef = useRef(null);

    useEffect(() => {
        if (!visible || !listRef.current) return;
        const active = listRef.current.querySelector('[data-active="true"]');
        if (active) {
            active.scrollIntoView({ block: 'nearest' });
        }
    }, [selectedIndex, visible]);

    if (!visible || items.length === 0) return null;

    const posClass = position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2';

    return (
        <div
            className={`absolute ${posClass} left-0 w-48 bg-white border border-border rounded-lg shadow-xl overflow-hidden animate-fade-in z-50 ${className}`}
        >
            <div
                ref={listRef}
                className="p-1.5 overflow-y-auto dropdown-scroll"
                style={{ maxHeight }}
            >
                {items.map((item, index) => {
                    const isActive = index === selectedIndex;

                    if (renderItem) {
                        return renderItem({ item, index, isActive, onSelect, onHover });
                    }

                    return (
                        <button
                            key={item.id ?? index}
                            data-active={isActive}
                            onClick={() => onSelect?.(item, index)}
                            onMouseEnter={() => onHover?.(index)}
                            className={`w-full px-2.5 py-1.5 text-left rounded-md transition-colors ${
                                isActive
                                    ? 'bg-teal-900/10'
                                    : 'hover:bg-gray-50'
                            }`}
                        >
                            {item.label && (
                                <div className={`text-sm font-medium ${
                                    isActive ? 'text-teal-900' : 'text-text-primary'
                                }`}>
                                    {item.label}
                                </div>
                            )}
                            {item.description && (
                                <div className="text-xs text-text-muted leading-tight truncate">
                                    {item.description}
                                </div>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
