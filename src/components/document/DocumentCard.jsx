import { useState } from 'react';
import { FiTrash2, FiAlignLeft } from 'react-icons/fi';
import { HiTrash } from 'react-icons/hi2';
import DocumentStatusBadge from './DocumentStatusBadge';
import { TableRow, TableCell } from '../ui/Table';
import Checkbox from '../ui/Checkbox';

function formatFileSize(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentCard({ document, selected, onToggleSelect, onView, onDelete, onViewOcr }) {
    const [hovered, setHovered] = useState(false);
    const date = new Date(document.createdAt).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
    });

    return (
        <TableRow onClick={() => onView(document)}>
            <TableCell>
                <div className="flex items-center justify-center">
                    <Checkbox
                        checked={!!selected}
                        onChange={e => { e.stopPropagation(); onToggleSelect(); }}
                        onClick={e => e.stopPropagation()}
                    />
                </div>
            </TableCell>
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
                <div className="flex items-center justify-end gap-0.5">
                    {document.isScanned && document.ocrStatus === 'completed' && (
                        <button
                            onClick={e => { e.stopPropagation(); onViewOcr(document); }}
                            className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                            title="View OCR result"
                        >
                            <FiAlignLeft size={15} />
                        </button>
                    )}
                    <button
                        onClick={e => { e.stopPropagation(); onDelete(document.id); }}
                        onMouseEnter={() => setHovered(true)}
                        onMouseLeave={() => setHovered(false)}
                        className="p-2 transition-colors rounded"
                        title="Delete"
                    >
                        {hovered
                            ? <HiTrash size={16} className="text-red-700" />
                            : <FiTrash2 size={16} className="text-gray-400" />
                        }
                    </button>
                </div>
            </TableCell>
        </TableRow>
    );
}
