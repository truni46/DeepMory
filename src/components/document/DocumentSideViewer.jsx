import { useState, useEffect, useCallback } from 'react';
import { FiX, FiFileText, FiDownload, FiZoomIn, FiZoomOut } from 'react-icons/fi';
import documentService from '../../services/documentService';
import PDFViewer from '../viewer/PDFViewer';
import WordViewer from '../viewer/WordViewer';
import ExcelViewer from '../viewer/ExcelViewer';
import TextViewer from '../viewer/TextViewer';
import TSVViewer from '../viewer/TSVViewer';
import MarkdownViewer from '../viewer/MarkdownViewer';

export default function DocumentSideViewer({ document, pageStart, pageEnd, onClose }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileError, setFileError] = useState(null);
    const [scale, setScale] = useState(1.0);

    // Compute initial page to scroll to (always the start of the range)
    const initialPage = pageStart ? parseInt(pageStart, 10) : 1;

    // Label shown in header
    const pageLabel = pageStart
        ? (pageEnd ? `Pages ${pageStart}–${pageEnd}` : `Page ${pageStart}`)
        : null;

    const zoomIn  = useCallback(() => setScale(s => Math.min(3.0, parseFloat((s + 0.1).toFixed(1)))), []);
    const zoomOut = useCallback(() => setScale(s => Math.max(0.2, parseFloat((s - 0.1).toFixed(1)))), []);

    // Safety check just in case document is malformed or just a filename skeleton
    const filename = document?.filename || document?.name || 'document';
    const fileType = document?.fileType || filename.split('.').pop().toLowerCase();

    const isPdf   = fileType === 'pdf';
    const isWord   = fileType === 'docx' || fileType === 'doc';
    const isExcel  = fileType === 'xlsx' || fileType === 'xls' || fileType === 'csv';
    const isText   = fileType === 'txt';
    const isTsv    = fileType === 'tsv';
    const isMarkdown = fileType === 'md';

    useEffect(() => {
        if (!document?.id) return;

        // Reset state when switching to a different document
        setFileUrl(null);
        setFileError(null);
        setScale(1.0);

        let objectUrl = null;
        documentService.getDocumentFileUrl(document.id)
            .then(url => {
                objectUrl = url;
                setFileUrl(url);
            })
            .catch(() => setFileError('Could not load file preview.'));

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [document?.id]);

    if (!document) return null;

    return (
        <div className="h-full flex flex-col bg-white border border-gray-300 shadow-xl overflow-hidden transition-all duration-300 m-3 rounded-2xl transform translate-x-0">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border-color bg-gray-50/50">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-white border shadow-sm flex-shrink-0">
                        {isPdf ? <FiFileText className="text-orange-500" /> :
                         isWord ? <FiFileText className="text-blue-500" /> :
                         isExcel ? <FiFileText className="text-green-500" /> :
                         <FiFileText className="text-gray-500" />}
                    </div>
                    <div className="flex flex-col min-w-0">
                        <h3 className="text-sm font-semibold text-text-primary truncate" title={filename}>
                            {filename}
                        </h3>
                        {pageLabel && (
                            <span className="text-[11px] font-medium text-text-secondary">{pageLabel}</span>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    {(isPdf || isWord) && (
                        <>
                            <button onClick={zoomOut} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom out (or Ctrl+Scroll)">
                                <FiZoomOut size={16} />
                            </button>
                            <span className="text-xs font-medium text-text-secondary w-10 text-center tabular-nums">
                                {Math.round(scale * 100)}%
                            </span>
                            <button onClick={zoomIn} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom in (or Ctrl+Scroll)">
                                <FiZoomIn size={16} />
                            </button>
                            <div className="w-px h-4 bg-gray-300 mx-1"></div>
                        </>
                    )}
                    <button
                        onClick={onClose}
                        className="p-1.5 text-text-secondary hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                        title="Close viewer"
                    >
                        <FiX size={18} />
                    </button>
                </div>
            </div>

            {/* Viewer Body */}
            <div className="flex-1 overflow-hidden relative bg-gray-100/50">
                {!document.id ? (
                    <div className="flex items-center justify-center h-full text-sm text-gray-400">
                        Unable to preview. No document provided.
                    </div>
                ) : fileError ? (
                    <div className="flex items-center justify-center h-full text-sm text-red-500">
                        {fileError}
                    </div>
                ) : isPdf ? (
                    <PDFViewer fileUrl={fileUrl} initialPage={initialPage} scale={scale} onScaleChange={setScale} />
                ) : isWord ? (
                    <WordViewer fileUrl={fileUrl} initialPage={initialPage} scale={scale} onScaleChange={setScale} />
                ) : isExcel ? (
                    <ExcelViewer fileUrl={fileUrl} />
                ) : isText ? (
                    <TextViewer fileUrl={fileUrl} />
                ) : isTsv ? (
                    <TSVViewer fileUrl={fileUrl} />
                ) : isMarkdown ? (
                    <MarkdownViewer fileUrl={fileUrl} />
                ) : (
                    <div className="flex flex-col items-center justify-center h-full gap-4">
                        <FiFileText size={48} className="text-gray-300" />
                        <p className="text-sm text-gray-500">
                            Preview not available for this file type.
                        </p>
                        <a
                            href={fileUrl}
                            download={filename}
                            className="px-4 py-2 bg-primary text-white rounded-lg text-sm flex items-center gap-2 hover:bg-primary-dark transition-colors"
                        >
                            <FiDownload size={16} />
                            Download
                        </a>
                    </div>
                )}
            </div>
        </div>
    );
}
