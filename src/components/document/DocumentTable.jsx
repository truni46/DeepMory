import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { FiSearch } from 'react-icons/fi';
import DocumentCard from './DocumentCard';
import DocumentDetailModal from './DocumentDetailModal';
import ConfirmDialog from '../ui/ConfirmDialog';
import Table from '../ui/Table';
import Checkbox from '../ui/Checkbox';
import documentService from '../../services/documentService';

const POLL_INTERVAL_MS = 3000;
const PAGE_SIZE = 10;

function hasProcessingDocs(docs) {
    return docs.some(
        d => d.embeddingStatus === 'processing' || d.embeddingStatus === 'pending',
    );
}

export default function DocumentTable({ refreshTrigger }) {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedDoc, setSelectedDoc] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [currentPage, setCurrentPage] = useState(1);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const pollingRef = useRef(null);

    const fetchDocuments = async (showLoading = false) => {
        if (showLoading) setLoading(true);
        try {
            const docs = await documentService.getDocuments();
            setDocuments(docs);
        } catch (err) {
            console.error('fetchDocuments failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments(true);
    }, []);

    useEffect(() => {
        if (refreshTrigger > 0) fetchDocuments(false);
    }, [refreshTrigger]);

    useEffect(() => {
        const needsPolling = hasProcessingDocs(documents);
        if (needsPolling && !pollingRef.current) {
            pollingRef.current = setInterval(async () => {
                try {
                    const docs = await documentService.getDocuments();
                    setDocuments(docs);
                    if (!hasProcessingDocs(docs)) {
                        clearInterval(pollingRef.current);
                        pollingRef.current = null;
                    }
                } catch (err) {
                    console.error('Polling failed:', err);
                }
            }, POLL_INTERVAL_MS);
        } else if (!needsPolling && pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    }, [documents]);

    useEffect(() => {
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        };
    }, []);

    const filteredDocs = useMemo(() => {
        if (!searchQuery.trim()) return documents;
        const q = searchQuery.toLowerCase();
        return documents.filter(doc =>
            doc.filename?.toLowerCase().includes(q) ||
            doc.fileType?.toLowerCase().includes(q)
        );
    }, [documents, searchQuery]);

    const totalPages = Math.max(1, Math.ceil(filteredDocs.length / PAGE_SIZE));

    useEffect(() => {
        setCurrentPage(1);
    }, [searchQuery]);

    const paginatedDocs = useMemo(() => {
        const start = (currentPage - 1) * PAGE_SIZE;
        return filteredDocs.slice(start, start + PAGE_SIZE);
    }, [filteredDocs, currentPage]);

    const allPageSelected = paginatedDocs.length > 0 && paginatedDocs.every(d => selectedIds.has(d.id));
    const somePageSelected = !allPageSelected && paginatedDocs.some(d => selectedIds.has(d.id));

    const toggleSelectAll = () => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (allPageSelected) {
                paginatedDocs.forEach(d => next.delete(d.id));
            } else {
                paginatedDocs.forEach(d => next.add(d.id));
            }
            return next;
        });
    };

    const toggleSelect = (id) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const [deleteTarget, setDeleteTarget] = useState(null);

    const handleDeleteRequest = useCallback((documentId) => {
        const doc = documents.find(d => d.id === documentId);
        setDeleteTarget({ id: documentId, filename: doc?.filename || 'this document' });
    }, [documents]);

    const handleDeleteConfirm = useCallback(async () => {
        if (!deleteTarget) return;
        try {
            await documentService.deleteDocument(deleteTarget.id);
            setDocuments(prev => prev.filter(d => d.id !== deleteTarget.id));
            setSelectedIds(prev => {
                const next = new Set(prev);
                next.delete(deleteTarget.id);
                return next;
            });
        } catch (err) {
            console.error('Delete failed:', err);
        } finally {
            setDeleteTarget(null);
        }
    }, [deleteTarget]);

    const handleDeleteCancel = useCallback(() => {
        setDeleteTarget(null);
    }, []);

    const buildPageNumbers = () => {
        const pages = [];
        if (totalPages <= 7) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
            return pages;
        }
        pages.push(1);
        if (currentPage > 3) pages.push('...');
        const start = Math.max(2, currentPage - 1);
        const end = Math.min(totalPages - 1, currentPage + 1);
        for (let i = start; i <= end; i++) pages.push(i);
        if (currentPage < totalPages - 2) pages.push('...');
        pages.push(totalPages);
        return pages;
    };

    const checkboxHeader = (
        <div className="flex items-center justify-center">
            <Checkbox checked={allPageSelected} indeterminate={somePageSelected} onChange={toggleSelectAll} variant="header" />
        </div>
    );

    return (
        <>
            <div className="relative mb-3 group">
                <FiSearch size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted transition-colors group-focus-within:text-gray-600" />
                <input
                    type="text"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    placeholder="Search documents..."
                    className="pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:bg-white focus:outline-none focus:border-gray-600 transition-colors w-64"
                />
            </div>
            <div className="bg-white rounded-xl border border-border-color overflow-hidden">

                {loading ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        Loading...
                    </div>
                ) : filteredDocs.length === 0 ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        {searchQuery ? 'No documents match your search.' : 'No documents uploaded yet.'}
                    </div>
                ) : (
                    <>
                        <Table headers={[checkboxHeader, 'Name', 'Type', 'Size', 'Status', 'Uploaded', 'Actions']}>
                            {paginatedDocs.map(doc => (
                                <DocumentCard
                                    key={doc.id}
                                    document={doc}
                                    selected={selectedIds.has(doc.id)}
                                    onToggleSelect={() => toggleSelect(doc.id)}
                                    onView={setSelectedDoc}
                                    onDelete={handleDeleteRequest}
                                />
                            ))}
                        </Table>

                        {totalPages > 1 && (
                            <div className="px-6 py-4 border-t border-border-color flex items-center justify-center gap-1">
                                <button
                                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                    disabled={currentPage === 1}
                                    className="px-3 py-1.5 text-sm rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    &lt;
                                </button>
                                {buildPageNumbers().map((page, i) =>
                                    page === '...' ? (
                                        <span key={`ellipsis-${i}`} className="px-2 py-1.5 text-sm text-text-muted">...</span>
                                    ) : (
                                        <button
                                            key={page}
                                            onClick={() => setCurrentPage(page)}
                                            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                                                currentPage === page
                                                    ? 'bg-primary text-white font-medium'
                                                    : 'hover:bg-gray-100 text-text-secondary'
                                            }`}
                                        >
                                            {page}
                                        </button>
                                    )
                                )}
                                <button
                                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                    disabled={currentPage === totalPages}
                                    className="px-3 py-1.5 text-sm rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    &gt;
                                </button>
                            </div>
                        )}
                    </>
                )}
            </div>

            {selectedDoc && (
                <DocumentDetailModal
                    document={selectedDoc}
                    onClose={() => setSelectedDoc(null)}
                />
            )}

            <ConfirmDialog
                open={!!deleteTarget}
                title="Delete document?"
                description={deleteTarget ? `"${deleteTarget.filename}" will be permanently deleted. This action cannot be undone.` : ''}
                confirmLabel="Delete"
                cancelLabel="Cancel"
                onConfirm={handleDeleteConfirm}
                onCancel={handleDeleteCancel}
            />
        </>
    );
}
