import { useState, useEffect, useRef } from 'react';
import { FiRefreshCw } from 'react-icons/fi';
import DocumentCard from './ui/DocumentCard';
import DocumentDetailModal from './ui/DocumentDetailModal';
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

    const fetchDocuments = async () => {
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
        setLoading(true);
        fetchDocuments();
    }, [refreshTrigger]);

    useEffect(() => {
        if (!hasProcessingDocs(documents)) return;

        pollingRef.current = setInterval(async () => {
            try {
                const docs = await documentService.getDocuments();
                setDocuments(docs);
                if (!hasProcessingDocs(docs)) {
                    clearInterval(pollingRef.current);
                }
            } catch (err) {
                console.error('Polling failed:', err);
            }
        }, POLL_INTERVAL_MS);

        return () => clearInterval(pollingRef.current);
    }, [documents]);

    const handleDelete = async documentId => {
        if (!window.confirm('Delete this document?')) return;
        try {
            await documentService.deleteDocument(documentId);
            setDocuments(prev => prev.filter(d => d.id !== documentId));
        } catch (err) {
            console.error('Delete failed:', err);
        }
    };

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
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-gray-50 text-text-secondary text-xs font-medium uppercase tracking-wide">
                                <tr>
                                    <th className="px-6 py-3">Name</th>
                                    <th className="px-6 py-3">Type</th>
                                    <th className="px-6 py-3">Size</th>
                                    <th className="px-6 py-3">Status</th>
                                    <th className="px-6 py-3">Uploaded</th>
                                    <th className="px-6 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {documents.map(doc => (
                                    <DocumentCard
                                        key={doc.id}
                                        document={doc}
                                        onView={setSelectedDoc}
                                        onDelete={handleDelete}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {selectedDoc && (
                <DocumentDetailModal
                    document={selectedDoc}
                    onClose={() => setSelectedDoc(null)}
                />
            )}
        </>
    );
}
