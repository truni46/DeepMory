import { useState, useEffect, useCallback } from 'react';
import { FiX, FiFileText, FiCalendar, FiBookOpen, FiDownload, FiZoomIn, FiZoomOut } from 'react-icons/fi';
import documentService from '../../services/documentService';
import PDFViewer from '../viewer/PDFViewer';
import WordViewer from '../viewer/WordViewer';
import ExcelViewer from '../viewer/ExcelViewer';
import TextViewer from '../viewer/TextViewer';
import TSVViewer from '../viewer/TSVViewer';
import MarkdownViewer from '../viewer/MarkdownViewer';
import DocumentStatusBadge from './DocumentStatusBadge';

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    });
}

export default function DocumentDetailModal({ document, onClose }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileError, setFileError] = useState(null);
    const [scale, setScale] = useState(1.0);

    const zoomIn  = useCallback(() => setScale(s => Math.min(3.0, parseFloat((s + 0.1).toFixed(1)))), []);
    const zoomOut = useCallback(() => setScale(s => Math.max(0.2, parseFloat((s - 0.1).toFixed(1)))), []);

    const fileType = document.fileType;
    const isPdf     = fileType === 'pdf';
    const isWord     = fileType === 'docx' || fileType === 'doc';
    const isExcel    = fileType === 'xlsx' || fileType === 'xls' || fileType === 'csv';
    const isText     = fileType === 'txt';
    const isTsv      = fileType === 'tsv';
    const isMarkdown = fileType === 'md';

    useEffect(() => {
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
    }, [document.id]);

    return (
        <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 pl-64"
            onClick={onClose}
            style={{ marginTop: '0px' }}
        >
            <div
                className="bg-white rounded-xl shadow-2xl w-[90vw] max-w-5xl h-[85vh] flex flex-col overflow-hidden"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between px-6 py-4 border-b border-border-color">
                    <h2 className="text-lg font-semibold">Document Preview</h2>
                    <div className="flex items-center gap-1">
                        {isPdf && (
                            <>
                                <button onClick={zoomOut} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom out (Ctrl+Scroll)">
                                    <FiZoomOut size={16} />
                                </button>
                                <span className="text-xs font-medium text-text-secondary w-10 text-center tabular-nums">
                                    {Math.round(scale * 100)}%
                                </span>
                                <button onClick={zoomIn} className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-gray-100 rounded-md transition-colors" title="Zoom in (Ctrl+Scroll)">
                                    <FiZoomIn size={16} />
                                </button>
                                <div className="w-px h-4 bg-gray-300 mx-1"></div>
                            </>
                        )}
                        <button
                            onClick={onClose}
                            className="p-2 rounded hover:bg-gray-100 transition-colors"
                        >
                            <FiX size={20} />
                        </button>
                    </div>
                </div>

                <div className="flex flex-1 overflow-hidden">
                    <div className="flex-1 border-r border-border-color overflow-hidden">
                        {fileError ? (
                            <div className="flex items-center justify-center h-full text-sm text-red-500">
                                {fileError}
                            </div>
                        ) : isPdf ? (
                            <PDFViewer fileUrl={fileUrl} scale={scale} onScaleChange={setScale} />
                        ) : isWord ? (
                            <WordViewer fileUrl={fileUrl} />
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
                                    download={document.filename}
                                    className="px-4 py-2 bg-primary text-white rounded-lg text-sm flex items-center gap-2 hover:bg-primary-dark transition-colors"
                                >
                                    <FiDownload size={16} />
                                    Download
                                </a>
                            </div>
                        )}
                    </div>

                    <div className="w-80 flex-shrink-0 overflow-y-auto p-6 space-y-6">
                        <h3 className="text-lg font-semibold break-words">
                            {document.filename}
                        </h3>

                        <div className="space-y-3 text-sm text-text-secondary">
                            {document.pageCount > 0 && (
                                <div className="flex items-center gap-2">
                                    <FiBookOpen size={16} />
                                    <span>
                                        Total pages:{' '}
                                        <strong className="text-text-primary">
                                            {document.pageCount}
                                        </strong>
                                    </span>
                                </div>
                            )}
                            <div className="flex items-center gap-2">
                                <FiCalendar size={16} />
                                <span>
                                    Uploaded on:{' '}
                                    <strong className="text-text-primary">
                                        {formatDate(document.createdAt)}
                                    </strong>
                                </span>
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="font-semibold text-sm">About this document</h4>
                                <DocumentStatusBadge status={document.summaryStatus} />
                            </div>

                            {document.summaryStatus === 'completed' && document.summary ? (
                                <p className="text-sm text-text-secondary leading-relaxed">
                                    {document.summary}
                                </p>
                            ) : document.summaryStatus === 'processing' ||
                              document.summaryStatus === 'pending' ? (
                                <div className="space-y-2">
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-full" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-4/5" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-3/4" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-2/3" />
                                </div>
                            ) : (
                                <p className="text-sm text-red-400">
                                    Summary generation failed.
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
