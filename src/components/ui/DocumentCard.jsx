// src/components/ui/DocumentCard.jsx
import { FiTrash2, FiEye } from 'react-icons/fi';
import DocumentStatusBadge from './DocumentStatusBadge';

const FILE_ICONS = {
    pdf:  '📄',
    docx: '📝',
    doc:  '📝',
    xlsx: '📊',
    xls:  '📊',
    txt:  '📃',
    md:   '📃',
};

function formatFileSize(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentCard({ document, onView, onDelete }) {
    const icon = FILE_ICONS[document.fileType] || '📄';
    const date = new Date(document.createdAt).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
    });

    return (
        <tr className="hover:bg-gray-50 transition-colors border-b border-border-color last:border-0">
            <td className="px-6 py-4">
                <div className="flex items-center gap-3">
                    <span className="text-lg">{icon}</span>
                    <span
                        className="font-medium text-sm truncate max-w-xs"
                        title={document.filename}
                    >
                        {document.filename}
                    </span>
                </div>
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary uppercase">
                {document.fileType || '—'}
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary">
                {formatFileSize(document.fileSize)}
            </td>
            <td className="px-6 py-4">
                <DocumentStatusBadge status={document.embeddingStatus} />
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary">{date}</td>
            <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                    <button
                        onClick={() => onView(document)}
                        className="p-2 text-gray-400 hover:text-primary transition-colors rounded hover:bg-primary/10"
                        title="View details"
                    >
                        <FiEye size={16} />
                    </button>
                    <button
                        onClick={() => onDelete(document.id)}
                        className="p-2 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-red-50"
                        title="Delete"
                    >
                        <FiTrash2 size={16} />
                    </button>
                </div>
            </td>
        </tr>
    );
}
