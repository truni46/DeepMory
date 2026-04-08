// src/components/DocumentUploadZone.jsx
import { useState, useRef, useCallback } from 'react';
import { FiUploadCloud, FiCheck, FiAlertCircle } from 'react-icons/fi';
import documentService from '../services/documentService';

const ACCEPTED = '.pdf,.txt,.md,.docx,.doc,.xlsx,.xls';
const MAX_CONCURRENT = 3;

function FileProgressItem({ item }) {
    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
                <span className="truncate max-w-xs text-text-secondary" title={item.file.name}>
                    {item.file.name}
                </span>
                <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                    {item.status === 'done' && <FiCheck size={14} className="text-green-600" />}
                    {item.status === 'error' && <FiAlertCircle size={14} className="text-red-500" />}
                    <span className="text-text-secondary">
                        {item.status === 'error' ? item.errorMessage : `${item.progress}%`}
                    </span>
                </div>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-200 ${
                        item.status === 'error'
                            ? 'bg-red-400'
                            : item.status === 'done'
                            ? 'bg-green-500'
                            : 'bg-primary'
                    }`}
                    style={{ width: `${item.progress}%` }}
                />
            </div>
        </div>
    );
}

export default function DocumentUploadZone({ onUploadComplete }) {
    const [dragOver, setDragOver] = useState(false);
    const [uploadItems, setUploadItems] = useState([]);
    const inputRef = useRef(null);

    const updateItem = useCallback((id, patch) => {
        setUploadItems(prev => prev.map(i => (i.id === id ? { ...i, ...patch } : i)));
    }, []);

    const uploadFile = useCallback(
        async item => {
            updateItem(item.id, { status: 'uploading', progress: 0 });
            try {
                const results = await documentService.uploadDocuments(
                    [item.file],
                    progress => updateItem(item.id, { progress }),
                );
                updateItem(item.id, {
                    status: 'done',
                    progress: 100,
                    documentId: results[0]?.id || null,
                });
            } catch (err) {
                updateItem(item.id, {
                    status: 'error',
                    errorMessage: err.message || 'Upload failed',
                });
            }
        },
        [updateItem],
    );

    const processQueue = useCallback(
        async items => {
            for (let i = 0; i < items.length; i += MAX_CONCURRENT) {
                await Promise.all(items.slice(i, i + MAX_CONCURRENT).map(uploadFile));
            }
            if (onUploadComplete) onUploadComplete();
        },
        [uploadFile, onUploadComplete],
    );

    const handleFiles = useCallback(
        files => {
            const newItems = Array.from(files).map(file => ({
                id: Math.random().toString(36).slice(2),
                file,
                progress: 0,
                status: 'queued',
                documentId: null,
                errorMessage: null,
            }));
            setUploadItems(prev => [...prev, ...newItems]);
            processQueue(newItems);
        },
        [processQueue],
    );

    const onDrop = useCallback(
        e => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
        },
        [handleFiles],
    );

    return (
        <div className="bg-white rounded-xl border border-border-color p-6 space-y-4">
            <div
                onDragOver={e => {
                    e.preventDefault();
                    setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-colors ${
                    dragOver
                        ? 'border-primary bg-primary/5'
                        : 'border-gray-300 hover:border-primary/50'
                }`}
            >
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                    <FiUploadCloud size={22} className="text-gray-500" />
                </div>
                <p className="font-medium text-sm">Upload Documents</p>
                <p className="text-xs text-text-secondary">
                    Drag & drop PDF files here, or click to browse
                </p>
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    multiple
                    accept={ACCEPTED}
                    onChange={e => handleFiles(e.target.files)}
                />
            </div>

            {uploadItems.length > 0 && (
                <div className="space-y-3 pt-2">
                    {uploadItems.map(item => (
                        <FileProgressItem key={item.id} item={item} />
                    ))}
                </div>
            )}
        </div>
    );
}
