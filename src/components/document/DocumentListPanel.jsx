import { useState } from 'react';
import { FiChevronDown, FiChevronUp, FiX, FiCheck } from 'react-icons/fi';

export default function DocumentListPanel({ selectedDocs, onToggle, onRemove }) {
    const [collapsed, setCollapsed] = useState(false);

    if (!selectedDocs || selectedDocs.length === 0) return null;

    const activeCount = selectedDocs.filter(d => d.active !== false).length;

    return (
        <div className="absolute left-3 top-3 z-30 bg-white border border-border rounded-xl shadow-lg overflow-hidden" style={{ minWidth: 180, maxWidth: 220 }}>
            {/* Header */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors border-b border-border"
            >
                <span className="text-xs font-semibold text-text-secondary">
                    {activeCount}/{selectedDocs.length} tài liệu đang dùng
                </span>
                {collapsed
                    ? <FiChevronDown size={12} className="text-text-muted flex-shrink-0" />
                    : <FiChevronUp size={12} className="text-text-muted flex-shrink-0" />
                }
            </button>

            {/* Document list */}
            {!collapsed && (
                <ul className="py-1">
                    {selectedDocs.map(doc => {
                        const isActive = doc.active !== false;
                        return (
                            <li
                                key={doc.id}
                                className="group flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50"
                            >
                                {/* Checkbox — toggles active */}
                                <button
                                    type="button"
                                    onClick={() => onToggle?.(doc.id)}
                                    className={`w-4 h-4 flex-shrink-0 rounded-md border flex items-center justify-center transition-colors ${
                                        isActive
                                            ? 'bg-primary border-primary text-white'
                                            : 'bg-white border-gray-300 hover:border-gray-400'
                                    }`}
                                    title={isActive ? `Bỏ dùng ${doc.filename}` : `Dùng lại ${doc.filename}`}
                                    aria-checked={isActive}
                                    role="checkbox"
                                >
                                    {isActive && <FiCheck size={10} strokeWidth={3} />}
                                </button>

                                {/* Filename — dimmed when inactive */}
                                <span
                                    className={`text-xs truncate flex-1 ${
                                        isActive ? 'text-text-primary' : 'text-text-muted line-through'
                                    }`}
                                    title={doc.filename}
                                >
                                    {doc.filename}
                                </span>

                                {/* Remove — gray X on right */}
                                <button
                                    type="button"
                                    onClick={() => onRemove?.(doc.id)}
                                    className="flex-shrink-0 p-0.5 rounded text-gray-300 opacity-0 group-hover:opacity-100 hover:text-red-500 hover:bg-red-50 transition-all"
                                    title={`Xóa ${doc.filename} khỏi danh sách`}
                                    aria-label={`Remove ${doc.filename}`}
                                >
                                    <FiX size={12} />
                                </button>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
