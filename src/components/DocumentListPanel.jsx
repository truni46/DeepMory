import { useState } from 'react';
import { FiX, FiChevronDown, FiChevronUp, FiFileText } from 'react-icons/fi';

function getFileColorConfig(filename) {
    const ext = filename?.split('.').pop().toLowerCase();
    if (ext === 'doc' || ext === 'docx') return { icon: 'bg-[#0084FF]', label: 'DOC' };
    if (ext === 'xls' || ext === 'xlsx' || ext === 'csv') return { icon: 'bg-green-500', label: 'XLS' };
    if (ext === 'pdf') return { icon: 'bg-[#ff6b00]', label: 'PDF' };
    return { icon: 'bg-gray-400', label: 'FILE' };
}

export default function DocumentListPanel({ selectedDocs, onRemove }) {
    const [collapsed, setCollapsed] = useState(false);

    if (!selectedDocs || selectedDocs.length === 0) return null;

    return (
        <div className="absolute left-3 top-3 z-30 bg-white border border-border rounded-xl shadow-lg overflow-hidden" style={{ minWidth: 180, maxWidth: 220 }}>
            {/* Header */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors border-b border-border"
            >
                <div className="flex items-center gap-1.5">
                    <FiFileText size={12} className="text-primary flex-shrink-0" />
                    <span className="text-xs font-semibold text-text-secondary">
                        {selectedDocs.length} tài liệu đã chọn
                    </span>
                </div>
                {collapsed
                    ? <FiChevronDown size={12} className="text-text-muted flex-shrink-0" />
                    : <FiChevronUp size={12} className="text-text-muted flex-shrink-0" />
                }
            </button>

            {/* Document list */}
            {!collapsed && (
                <ul className="py-1">
                    {selectedDocs.map(doc => {
                        const { icon, label } = getFileColorConfig(doc.filename);
                        return (
                            <li key={doc.id} className="flex items-center gap-2 px-3 py-1.5 group hover:bg-gray-50">
                                <div className={`w-5 h-5 rounded flex-shrink-0 flex items-center justify-center ${icon}`}>
                                    <span className="text-[7px] text-white font-bold leading-none">{label}</span>
                                </div>
                                <span className="text-xs text-text-primary truncate flex-1" title={doc.filename}>
                                    {doc.filename}
                                </span>
                                <button
                                    onClick={(e) => { e.stopPropagation(); onRemove(doc.id); }}
                                    className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-gray-200 rounded text-text-muted transition-opacity flex-shrink-0"
                                    title={`Bỏ chọn ${doc.filename}`}
                                >
                                    <FiX size={11} />
                                </button>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
