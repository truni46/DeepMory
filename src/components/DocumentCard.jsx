// src/components/DocumentCard.jsx
import { FiTrash2 } from 'react-icons/fi';
import DocumentStatusBadge from './DocumentStatusBadge';
import { TableRow, TableCell } from './ui/Table';

function formatFileSize(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentCard({ document, onView, onDelete }) {
    const date = new Date(document.createdAt).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
    });

    return (
        <TableRow onClick={() => onView(document)}>
            <TableCell>
                <div className="flex items-center gap-3">
                    <span
                        className="font-medium text-sm truncate max-w-xs"
                        title={document.filename}
                    >
                        {document.filename}
                    </span>
                </div>
            </TableCell>
            <TableCell className="text-sm text-text-secondary uppercase">
                {document.fileType || '—'}
            </TableCell>
            <TableCell className="text-sm text-text-secondary">
                {formatFileSize(document.fileSize)}
            </TableCell>
            <TableCell>
                <DocumentStatusBadge status={document.embeddingStatus} />
            </TableCell>
            <TableCell className="text-sm text-text-secondary">
                {date}
            </TableCell>
            <TableCell isLast>
                <div className="flex items-center justify-end">
                    <button
                        onClick={e => { e.stopPropagation(); onDelete(document.id); }}
                        className="p-2 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-red-50"
                        title="Delete"
                    >
                        <FiTrash2 size={16} />
                    </button>
                </div>
            </TableCell>
        </TableRow>
    );
}
