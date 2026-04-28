import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import documentService from '../../services/documentService';
import DocumentUploadZone from './DocumentUploadZone';

function formatDate(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString();
}

export default function DocumentPickerModal({ onConfirm, onClose, selectedIds = [] }) {
    const [documents, setDocuments] = useState([]);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [localSelected, setLocalSelected] = useState(new Set(selectedIds));
    const cardRef = useRef(null);
    const searchRef = useRef(null);
    const navigate = useNavigate();

    const [isUploading, setIsUploading] = useState(false);

    const loadDocs = async () => {
        setLoading(true);
        try {
            const docs = await documentService.getDocuments();
            setDocuments(docs || []);
        } catch (e) {
            console.error('DocumentPickerModal: failed to load documents', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDocs();
    }, []);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (cardRef.current && !cardRef.current.contains(e.target)) {
                onClose();
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onClose]);

    const toggleDoc = (docId) => {
        setLocalSelected(prev => {
            const next = new Set(prev);
            if (next.has(docId)) next.delete(docId);
            else next.add(docId);
            return next;
        });
    };

    const handleConfirm = () => {
        const confirmedDocs = documents.filter(d => localSelected.has(d.id));
        onConfirm(confirmedDocs);
        onClose();
    };

    const filtered = documents.filter(d =>
        d.filename?.toLowerCase().includes(query.toLowerCase())
    );

    return (
        <div
            ref={cardRef}
            className="fixed bottom-[130px] left-1/2 -translate-x-1/2 w-[360px] max-w-[calc(100vw-32px)] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col z-50 overflow-hidden"
            style={{ maxHeight: '420px' }}
        >
            <div className="flex items-center gap-1.5 px-4 py-3 border-b border-gray-100 pointer-events-auto">
                {isUploading ? (
                    <button
                        onClick={() => {
                            setIsUploading(false);
                            loadDocs();
                        }}
                        className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 transition-colors"
                    >
                        <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                        </svg>
                        Back to Documents
                    </button>
                ) : (
                    <>
                        <svg className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                        </svg>
                        <span className="text-xs text-gray-400">Root</span>
                        <svg className="w-3 h-3 text-gray-300 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        <span className="text-xs font-medium text-gray-700">My Documents</span>
                    </>
                )}
            </div>

            <div className="overflow-y-auto flex-1">
                {isUploading ? (
                    <div className="p-4">
                        <DocumentUploadZone onUploadComplete={() => {}} />
                    </div>
                ) : loading ? (
                    <div className="flex items-center justify-center py-10 text-gray-400 text-sm gap-2">
                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Loading...
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 text-gray-400 text-sm gap-1">
                        <span className="text-2xl">📂</span>
                        <span>{query ? 'No documents match.' : 'No documents in your library.'}</span>
                    </div>
                ) : (
                    <ul>
                        {filtered.map(doc => {
                            const isSelected = localSelected.has(doc.id);
                            return (
                                <li key={doc.id}>
                                    <button
                                        onClick={() => toggleDoc(doc.id)}
                                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-50 ${isSelected ? 'bg-blue-50/60' : ''}`}
                                    >
                                        <div className="w-8 h-8 flex-shrink-0 bg-gray-100 rounded-md flex items-center justify-center">
                                            <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                            </svg>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-medium text-gray-800 truncate">{doc.filename}</p>
                                            <p className="text-xs text-gray-400 mt-0.5">
                                                {doc.pageCount > 0 ? `${doc.pageCount} pages` : '... pages'}
                                                {doc.createdAt ? ` · ${formatDate(doc.createdAt)}` : ''}
                                            </p>
                                        </div>
                                        {isSelected && (
                                            <svg className="w-4 h-4 text-gray-700 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                            </svg>
                                        )}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>

            {!isUploading && (
                <>
            <div className="border-t border-gray-100 px-3 py-2 flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                    ref={searchRef}
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder="Search documents..."
                    className="flex-1 text-xs outline-none text-gray-700 placeholder:text-gray-400 bg-transparent"
                />
                <button
                    onClick={() => setIsUploading(true)}
                    className="flex items-center gap-1 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors flex-shrink-0"
                >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    Upload
                </button>
            </div>

            <div className="border-t border-gray-100 px-3 py-2 flex items-center justify-between">
                <button
                    onClick={handleConfirm}
                    className="flex items-center gap-1.5 text-xs text-gray-700 hover:text-gray-900 transition-colors"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    <span>Add documents</span>
                    {localSelected.size > 0 && (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-bold">
                            {localSelected.size}
                        </span>
                    )}
                </button>
                <button
                    onClick={onClose}
                    className="p-1.5 rounded-full hover:bg-gray-100 transition-colors text-gray-400"
                    title="Close"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                </button>
            </div>
                </>
            )}
        </div>
    );
}
