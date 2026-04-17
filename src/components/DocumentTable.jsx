import { useState, useEffect, useRef, useCallback } from 'react';
import { FiRefreshCw } from 'react-icons/fi';
import DocumentCard from './DocumentCard';
import DocumentDetailModal from './DocumentDetailModal';
import ConfirmDialog from './ui/ConfirmDialog';
import Table from './ui/Table';
import documentService from '../services/documentService';

const POLL_INTERVAL_MS = 3000;

function hasProcessingDocs(docs) {
    return docs.some(
        d => d.embeddingStatus === 'processing' || d.embeddingStatus === 'pending',
    );
}

export default function DocumentTable({ refreshTrigger }) {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedDoc, setSelectedDoc] = useState(null);
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

    // Initial load
    useEffect(() => {
        fetchDocuments(true);
    }, []);

    // Refresh when new upload completes — no loading spinner
    useEffect(() => {
        if (refreshTrigger > 0) fetchDocuments(false);
    }, [refreshTrigger]);

    // Polling: start when there are processing docs, stop when all done
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
        } catch (err) {
            console.error('Delete failed:', err);
        } finally {
            setDeleteTarget(null);
        }
    }, [deleteTarget]);

    const handleDeleteCancel = useCallback(() => {
        setDeleteTarget(null);
    }, []);

    return (
        <>
            <div className="bg-white rounded-xl border border-border-color overflow-hidden">
                <div className="px-6 py-4 border-b border-border-color bg-gray-50 flex justify-between items-center">
                    <h2 className="text-lg font-semibold">My Documents</h2>
                    <div className="flex items-center gap-3">
                        <span className="text-sm text-text-secondary">
                            {documents.length} document{documents.length !== 1 ? 's' : ''}
                        </span>
                        <button
                            onClick={fetchDocuments}
                            className="p-1.5 text-text-secondary hover:text-primary transition-colors"
                            title="Refresh"
                        >
                            <FiRefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                </div>

                {loading ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        Loading...
                    </div>
                ) : documents.length === 0 ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        No documents uploaded yet.
                    </div>
                ) : (
                    <Table headers={['Name', 'Type', 'Size', 'Status', 'Uploaded', 'Actions']}>
                        {documents.map(doc => (
                            <DocumentCard
                                key={doc.id}
                                document={doc}
                                onView={setSelectedDoc}
                                onDelete={handleDeleteRequest}
                            />
                        ))}
                    </Table>
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
