// src/components/ui/PDFViewer.jsx
import { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

export default function PDFViewer({ fileUrl }) {
    const [numPages, setNumPages] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages);
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-gray-100">
            <div className="flex-1 overflow-y-auto flex justify-center p-4">
                <Document
                    file={fileUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={
                        <p className="text-sm text-gray-500 mt-8">Loading document...</p>
                    }
                    error={
                        <p className="text-sm text-red-500 mt-8">Failed to load PDF.</p>
                    }
                >
                    <Page pageNumber={currentPage} width={560} />
                </Document>
            </div>

            {numPages && (
                <div className="flex items-center justify-center gap-4 py-3 border-t border-gray-200 bg-white text-sm">
                    <button
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage <= 1}
                        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100 transition-colors"
                    >
                        ←
                    </button>
                    <span className="text-text-secondary">
                        {currentPage} / {numPages}
                    </span>
                    <button
                        onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                        disabled={currentPage >= numPages}
                        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100 transition-colors"
                    >
                        →
                    </button>
                </div>
            )}
        </div>
    );
}
