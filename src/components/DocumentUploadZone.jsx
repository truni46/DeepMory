// src/components/DocumentUploadZone.jsx
import { useState, useRef, useCallback, useEffect } from 'react';
import { FiUploadCloud, FiCheck, FiAlertCircle, FiPause, FiPlay, FiX } from 'react-icons/fi';
import { CgSpinner } from 'react-icons/cg';
import documentService from '../services/documentService';
import { useToast } from '../context/ToastContext';

const ACCEPTED = '.pdf,.txt,.md,.docx,.doc,.xlsx,.xls';
const MAX_CONCURRENT = 3;
const POLL_INTERVAL = 2000;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function FileProgressItem({ item, onPause, onResume, onCancel }) {
    const isActive = item.status === 'uploading' || item.status === 'indexing';
    const isPaused = item.status === 'paused';
    const showControls = isActive || isPaused;
    const currentProgress = item.phase === 'index' ? 100 : item.progress;

    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
                <span className="truncate max-w-xs text-text-secondary" title={item.file.name}>
                    {item.file.name}
                </span>
                <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                    {item.status === 'done' && (
                        <>
                            <FiCheck size={14} className="text-green-600" />
                            <span className="text-green-600">100%</span>
                        </>
                    )}
                    {item.status === 'error' && (
                        <>
                            <FiAlertCircle size={14} className="text-red-500" />
                            <span className="text-text-secondary">{item.errorMessage}</span>
                        </>
                    )}
                    {(isActive || isPaused) && item.phase === 'upload' && (
                        <>
                            <span className="text-text-secondary">Uploading</span>
                            <span className="text-gray-300">|</span>
                            <FiCheck size={12} className="text-green-500" />
                            <span className="text-text-secondary">{item.progress}%</span>
                        </>
                    )}
                    {(isActive || isPaused) && item.phase === 'index' && (
                        <>
                            <CgSpinner size={14} className={`text-primary ${isPaused ? '' : 'animate-spin'}`} />
                            <span className="text-text-secondary">{isPaused ? 'Paused' : 'Indexing...'}</span>
                        </>
                    )}
                    {showControls && (
                        <div className="flex items-center gap-1 ml-1.5">
                            {isPaused ? (
                                <button
                                    onClick={() => onResume(item.id)}
                                    className="w-5 h-5 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-colors"
                                    title="Resume"
                                >
                                    <FiPlay size={10} />
                                </button>
                            ) : (
                                <button
                                    onClick={() => onPause(item.id)}
                                    className="w-5 h-5 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-colors"
                                    title="Pause"
                                >
                                    <FiPause size={10} />
                                </button>
                            )}
                            <button
                                onClick={() => onCancel(item.id)}
                                className="w-5 h-5 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 transition-colors"
                                title="Cancel"
                            >
                                <FiX size={10} />
                            </button>
                        </div>
                    )}
                </div>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-300 ${
                        item.status === 'error'
                            ? 'bg-red-400'
                            : 'bg-green-500'
                    }`}
                    style={{ width: `${currentProgress}%` }}
                />
            </div>
        </div>
    );
}

export default function DocumentUploadZone({ onUploadComplete }) {
    const [dragOver, setDragOver] = useState(false);
    const [uploadItems, setUploadItems] = useState([]);
    const inputRef = useRef(null);
    const toast = useToast();
    const xhrMapRef = useRef({});
    const abortFlagsRef = useRef({});
    const pauseFlagsRef = useRef({});

    useEffect(() => {
        return () => {
            Object.values(xhrMapRef.current).forEach(xhr => xhr.abort());
            Object.keys(abortFlagsRef.current).forEach(id => {
                abortFlagsRef.current[id] = true;
            });
        };
    }, []);

    const updateItem = useCallback((id, patch) => {
        setUploadItems(prev => prev.map(i => (i.id === id ? { ...i, ...patch } : i)));
    }, []);

    const removeItem = useCallback((id) => {
        setUploadItems(prev => prev.filter(i => i.id !== id));
    }, []);

    const handlePause = useCallback((id) => {
        pauseFlagsRef.current[id] = true;
        if (xhrMapRef.current[id]) {
            xhrMapRef.current[id].abort();
            delete xhrMapRef.current[id];
        }
        setUploadItems(prev => prev.map(i =>
            i.id === id ? { ...i, status: 'paused' } : i
        ));
    }, []);

    const handleCancel = useCallback((id) => {
        abortFlagsRef.current[id] = true;
        pauseFlagsRef.current[id] = false;
        if (xhrMapRef.current[id]) {
            xhrMapRef.current[id].abort();
            delete xhrMapRef.current[id];
        }
        removeItem(id);
    }, [removeItem]);

    const pollIndexingStatus = useCallback(
        async (itemId, documentId) => {
            try {
                while (true) {
                    if (abortFlagsRef.current[itemId]) break;
                    if (pauseFlagsRef.current[itemId]) {
                        await sleep(500);
                        continue;
                    }

                    await sleep(POLL_INTERVAL);
                    if (abortFlagsRef.current[itemId]) break;

                    const doc = await documentService.getDocument(documentId);
                    if (!doc) continue;

                    if (doc.embeddingStatus === 'completed') {
                        updateItem(itemId, { status: 'done' });
                        toast.success('Digitization successfully');
                        if (onUploadComplete) onUploadComplete();
                        setTimeout(() => removeItem(itemId), 800);
                        break;
                    }

                    if (doc.embeddingStatus === 'failed') {
                        updateItem(itemId, {
                            status: 'error',
                            errorMessage: doc.embeddingError || 'Indexing failed',
                        });
                        break;
                    }
                }
            } catch (err) {
                if (!abortFlagsRef.current[itemId]) {
                    updateItem(itemId, {
                        status: 'error',
                        errorMessage: err.message || 'Polling failed',
                    });
                }
            } finally {
                delete abortFlagsRef.current[itemId];
                delete pauseFlagsRef.current[itemId];
            }
        },
        [updateItem, removeItem, toast, onUploadComplete],
    );

    const uploadFile = useCallback(
        async item => {
            updateItem(item.id, { status: 'uploading', progress: 0, phase: 'upload' });
            abortFlagsRef.current[item.id] = false;
            pauseFlagsRef.current[item.id] = false;

            try {
                const results = await documentService.uploadDocuments(
                    [item.file],
                    progress => updateItem(item.id, { progress }),
                    'personal',
                    (xhr) => { xhrMapRef.current[item.id] = xhr; },
                );
                delete xhrMapRef.current[item.id];

                if (abortFlagsRef.current[item.id]) return;

                const documentId = results[0]?.id || null;
                updateItem(item.id, {
                    status: 'indexing',
                    phase: 'index',
                    progress: 100,
                    documentId,
                });

                if (documentId) {
                    pollIndexingStatus(item.id, documentId);
                } else {
                    updateItem(item.id, {
                        status: 'error',
                        errorMessage: 'No document ID returned',
                    });
                }
            } catch (err) {
                if (!abortFlagsRef.current[item.id] && !pauseFlagsRef.current[item.id]) {
                    updateItem(item.id, {
                        status: 'error',
                        errorMessage: err.message || 'Upload failed',
                    });
                }
            }
        },
        [updateItem, pollIndexingStatus],
    );

    const handleResume = useCallback((id) => {
        pauseFlagsRef.current[id] = false;
        setUploadItems(prev => {
            const item = prev.find(i => i.id === id);
            if (!item) return prev;

            if (item.phase === 'index') {
                return prev.map(i => i.id === id ? { ...i, status: 'indexing' } : i);
            }

            uploadFile({ ...item, status: 'uploading' });
            return prev.map(i => i.id === id ? { ...i, status: 'uploading' } : i);
        });
    }, [uploadFile]);

    const processQueue = useCallback(
        async items => {
            for (let i = 0; i < items.length; i += MAX_CONCURRENT) {
                await Promise.all(items.slice(i, i + MAX_CONCURRENT).map(uploadFile));
            }
        },
        [uploadFile],
    );

    const handleFiles = useCallback(
        files => {
            const newItems = Array.from(files).map(file => ({
                id: Math.random().toString(36).slice(2),
                file,
                progress: 0,
                indexProgress: 0,
                phase: 'upload',
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
                <p className="text-xs text-text-secondary text-center">
                    Drag and drop files here, or click to browse
                </p>
                <p className="text-xs text-text-secondary text-center">
                    PDF, DOCX, XLSX, TXT, MD &nbsp;·&nbsp; Max 50 MB per file
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
                        <FileProgressItem
                            key={item.id}
                            item={item}
                            onPause={handlePause}
                            onResume={handleResume}
                            onCancel={handleCancel}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
