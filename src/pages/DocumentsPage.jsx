import React, { useState, useEffect } from 'react';
import { documentService } from '../services/documentService';
import { FiUpload, FiTrash2, FiFileText, FiRefreshCw } from 'react-icons/fi';

export default function DocumentsPage() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        setLoading(true);
        try {
            const docs = await documentService.getDocuments();
            setDocuments(docs);
            setError(null);
        } catch (err) {
            console.error('Failed to fetch documents:', err);
            setError('Failed to load documents. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);
        setError(null);

        try {
            await documentService.uploadDocument(file);
            await fetchDocuments();
        } catch (err) {
            console.error('Upload failed:', err);
            setError('Failed to upload document.');
        } finally {
            setUploading(false);
            // Reset file input
            event.target.value = '';
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Are you sure you want to delete this document?')) return;

        try {
            await documentService.deleteDocument(id);
            setDocuments(documents.filter(doc => doc.id !== id));
        } catch (err) {
            console.error('Delete failed:', err);
            setError('Failed to delete document.');
        }
    };

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden">
            <header className="px-6 py-4 border-b border-border-color bg-white flex justify-between items-center shadow-sm">
                <h1 className="text-2xl font-bold text-primary">My Documents</h1>
                <button
                    onClick={fetchDocuments}
                    className="p-2 text-text-secondary hover:text-primary transition-colors"
                    title="Refresh list"
                >
                    <FiRefreshCw className={loading ? 'animate-spin' : ''} />
                </button>
            </header>

            <main className="flex-1 overflow-y-auto p-8">
                <div className="max-w-4xl mx-auto space-y-8">

                    {/* Upload Section */}
                    <div className="bg-white rounded-xl shadow-sm p-6 border border-border-color">
                        <h2 className="text-lg font-semibold mb-4">Upload New Document</h2>
                        <div className="flex items-center gap-4">
                            <label className={`
                  flex items-center gap-2 px-6 py-3 rounded-lg cursor-pointer transition-all
                  ${uploading ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-primary text-white hover:bg-primary-dark shadow-md hover:shadow-lg'}
                `}>
                                <FiUpload />
                                <span>{uploading ? 'Uploading...' : 'Select Document'}</span>
                                <input
                                    type="file"
                                    className="hidden"
                                    onChange={handleFileUpload}
                                    disabled={uploading}
                                    accept=".pdf,.txt,.md,.docx,.doc,.xlsx,.xls"
                                />
                            </label>
                            {uploading && <span className="text-sm text-text-secondary animate-pulse">Processing file...</span>}
                        </div>
                        {error && <div className="mt-4 text-red-500 bg-red-50 p-3 rounded-lg text-sm">{error}</div>}
                    </div>

                    {/* Documents List */}
                    <div className="bg-white rounded-xl shadow-sm border border-border-color overflow-hidden">
                        <div className="px-6 py-4 border-b border-border-color bg-gray-50 flex justify-between items-center">
                            <h2 className="text-lg font-semibold">Uploaded Files</h2>
                            <span className="text-sm text-text-secondary">{documents.length} documents</span>
                        </div>

                        {documents.length === 0 ? (
                            <div className="p-12 text-center text-text-secondary flex flex-col items-center gap-3">
                                <FiFileText className="w-12 h-12 text-gray-300" />
                                <p>No documents uploaded yet.</p>
                            </div>
                        ) : (
                            <table className="w-full text-left">
                                <thead className="bg-gray-50 text-text-secondary text-sm font-medium">
                                    <tr>
                                        <th className="px-6 py-3">Name</th>
                                        <th className="px-6 py-3">Type</th>
                                        <th className="px-6 py-3">Status</th>
                                        <th className="px-6 py-3">Date</th>
                                        <th className="px-6 py-3 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border-color">
                                    {documents.map((doc) => (
                                        <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                                            <td className="px-6 py-4 font-medium flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                                                    <FiFileText />
                                                </div>
                                                {doc.filename}
                                            </td>
                                            <td className="px-6 py-4 text-sm text-text-secondary uppercase">{doc.file_type?.replace('.', '') || 'UNKNOWN'}</td>
                                            <td className="px-6 py-4 text-sm">
                                                <span className={`px-2 py-1 rounded-full text-xs font-medium 
                            ${doc.embedding_status === 'completed' ? 'bg-green-100 text-green-700' :
                                                        doc.embedding_status === 'failed' ? 'bg-red-100 text-red-700' :
                                                            'bg-yellow-100 text-yellow-700'}`}>
                                                    {doc.embedding_status || 'Pending'}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-sm text-text-secondary">
                                                {new Date(doc.created_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <button
                                                    onClick={() => handleDelete(doc.id)}
                                                    className="p-2 text-gray-400 hover:text-red-500 transition-colors rounded-full hover:bg-red-50"
                                                    title="Delete"
                                                >
                                                    <FiTrash2 />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
