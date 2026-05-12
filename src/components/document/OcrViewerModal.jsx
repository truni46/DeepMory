import { useState, useEffect, useCallback } from 'react';
import { FiX, FiCopy, FiCheck, FiZoomIn, FiZoomOut, FiAlignLeft } from 'react-icons/fi';
import documentService from '../../services/documentService';
import PDFViewer from '../viewer/PDFViewer';

function ImageViewer({ fileUrl }) {
    if (!fileUrl) return (
        <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading...</div>
    );
    return (
        <div className="flex items-center justify-center h-full overflow-auto bg-gray-100 p-4">
            <img src={fileUrl} alt="Document" className="max-w-full object-contain shadow-md rounded" />
        </div>
    );
}

function OcrTextPanel({ text, loading, error }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(() => {
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    }, [text]);

    // Parse page markers written by saveOcrText: "=== Page N ===\n..."
    const pages = text
        ? (() => {
            const parts = text.split(/^=== Page (\d+) ===\s*$/m);
            // parts = [before, pageNum, content, pageNum, content, ...]
            const result = [];
            for (let i = 1; i < parts.length; i += 2) {
                const pageNum = parseInt(parts[i], 10);
                const content = (parts[i + 1] || '').trim();
                result.push({ pageNum, content });
            }
            // fallback: old format without markers — treat as single block
            if (result.length === 0 && text.trim()) {
                result.push({ pageNum: null, content: text.trim() });
            }
            return result;
        })()
        : [];

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 bg-gray-50/60 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <FiAlignLeft size={14} className="text-indigo-500" />
                    <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">OCR Result</span>
                    {text && (
                        <span className="text-xs text-text-muted bg-gray-100 px-1.5 py-0.5 rounded">
                            {text.length.toLocaleString()} chars
                        </span>
                    )}
                </div>
                <button
                    onClick={handleCopy}
                    disabled={!text}
                    className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-text-secondary"
                    title="Copy all text"
                >
                    {copied ? <FiCheck size={12} className="text-green-500" /> : <FiCopy size={12} />}
                    {copied ? 'Copied' : 'Copy'}
                </button>
            </div>

            <div className="flex-1 overflow-auto custom-scrollbar bg-white">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3">
                        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                        <p className="text-sm text-text-secondary">Loading OCR text...</p>
                    </div>
                ) : error ? (
                    <div className="flex items-center justify-center h-full px-6">
                        <p className="text-sm text-red-400 text-center">{error}</p>
                    </div>
                ) : pages.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                        <p className="text-sm text-gray-400">No OCR text available.</p>
                    </div>
                ) : (
                    <div className="p-5 space-y-0">
                        {pages.map(({ pageNum, content }, i) => (
                            <div key={i}>
                                {i > 0 && <div className="h-px bg-gray-100 my-4" />}
                                {pageNum !== null && (
                                    <div className="flex items-center gap-2 mb-2 select-none">
                                        <span className="text-[10px] font-semibold text-indigo-400 bg-indigo-50 px-2 py-0.5 rounded-full">
                                            Page {pageNum}
                                        </span>
                                    </div>
                                )}
                                <pre className="text-sm leading-relaxed text-gray-800 whitespace-pre-wrap break-words font-[inherit]">
                                    {content || <span className="text-gray-300 italic">(empty)</span>}
                                </pre>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export default function OcrViewerModal({ document, onClose }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileError, setFileError] = useState(null);
    const [scale, setScale] = useState(1.0);
    const [ocrText, setOcrText] = useState('');
    const [ocrLoading, setOcrLoading] = useState(true);
    const [ocrError, setOcrError] = useState(null);

    const zoomIn  = useCallback(() => setScale(s => Math.min(3.0, parseFloat((s + 0.1).toFixed(1)))), []);
    const zoomOut = useCallback(() => setScale(s => Math.max(0.2, parseFloat((s - 0.1).toFixed(1)))), []);

    const fileType = document?.fileType || '';
    const isPdf    = fileType === 'pdf';
    const isImage  = ['png', 'jpg', 'jpeg', 'bmp', 'webp', 'tiff'].includes(fileType);

    useEffect(() => {
        let objectUrl = null;
        documentService.getDocumentFileUrl(document.id)
            .then(url => { objectUrl = url; setFileUrl(url); })
            .catch(() => setFileError('Could not load original file.'));
        return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
    }, [document.id]);

    useEffect(() => {
        setOcrLoading(true);
        setOcrError(null);
        documentService.getDocumentOcrText(document.id)
            .then(data => setOcrText(data.text || ''))
            .catch(() => setOcrError('OCR text not available for this document.'))
            .finally(() => setOcrLoading(false));
    }, [document.id]);

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 pl-64"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-xl shadow-2xl w-[92vw] max-w-7xl h-[90vh] flex flex-col overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-3 border-b border-border-color flex-shrink-0">
                    <div className="flex items-center gap-2.5 min-w-0">
                        <span className="flex-shrink-0 bg-indigo-100 text-indigo-700 px-2 py-0.5 text-xs rounded font-semibold tracking-wide">
                            OCR
                        </span>
                        <h2 className="text-sm font-semibold truncate" title={document.filename}>
                            {document.filename}
                        </h2>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                        {isPdf && (
                            <>
                                <button onClick={zoomOut} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom out">
                                    <FiZoomOut size={15} />
                                </button>
                                <span className="text-xs font-medium text-text-secondary w-10 text-center tabular-nums">
                                    {Math.round(scale * 100)}%
                                </span>
                                <button onClick={zoomIn} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom in">
                                    <FiZoomIn size={15} />
                                </button>
                                <div className="w-px h-4 bg-gray-200 mx-1" />
                            </>
                        )}
                        <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-md transition-colors text-text-secondary">
                            <FiX size={18} />
                        </button>
                    </div>
                </div>

                {/* Sub-header labels */}
                <div className="flex border-b border-border-color flex-shrink-0">
                    <div className="flex-[3] px-5 py-2 border-r border-border-color bg-gray-50/50">
                        <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Original Document</span>
                    </div>
                    <div className="flex-[2] px-5 py-2 bg-gray-50/50">
                        <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">OCR Extracted Text</span>
                    </div>
                </div>

                {/* Split body */}
                <div className="flex flex-1 overflow-hidden">
                    {/* Left: original document */}
                    <div className="flex-[3] border-r border-border-color overflow-hidden">
                        {fileError ? (
                            <div className="flex items-center justify-center h-full text-sm text-red-400">
                                {fileError}
                            </div>
                        ) : isPdf ? (
                            <PDFViewer fileUrl={fileUrl} scale={scale} onScaleChange={setScale} />
                        ) : isImage ? (
                            <ImageViewer fileUrl={fileUrl} />
                        ) : (
                            <div className="flex items-center justify-center h-full text-sm text-gray-400">
                                Preview not available for this file type.
                            </div>
                        )}
                    </div>

                    {/* Right: OCR text */}
                    <div className="flex-[2] overflow-hidden">
                        <OcrTextPanel text={ocrText} loading={ocrLoading} error={ocrError} />
                    </div>
                </div>
            </div>
        </div>
    );
}
