// src/components/ui/PDFViewer.jsx
import { useState, useRef, useEffect, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

export default function PDFViewer({ fileUrl, initialPage = 1, scale = 1.0, onScaleChange }) {
    const [numPages, setNumPages] = useState(null);
    const [visiblePage, setVisiblePage] = useState(initialPage);
    const [pageInput, setPageInput] = useState('');
    const [zoomInput, setZoomInput] = useState(Math.round(scale * 100).toString());
    const scrollContainerRef = useRef(null);
    const observerRef = useRef(null);

    const scrollToPage = useCallback((pageNum) => {
        const pageElement = document.getElementById(`pdf-page-${pageNum}`);
        if (pageElement) {
            pageElement.scrollIntoView({ behavior: 'auto', block: 'start' });
        }
    }, []);
    console.log("test")
    // Keep zoomInput in sync with external scale changes (from header buttons)
    useEffect(() => {
        setZoomInput(Math.round(scale * 100).toString());
    }, [scale]);

    const setScale = useCallback((updater) => {
        if (!onScaleChange) return;
        const next = typeof updater === 'function' ? updater(scale) : updater;
        const clamped = Math.min(3.0, Math.max(0.2, parseFloat(next.toFixed(1))));
        onScaleChange(clamped);
    }, [onScaleChange, scale]);

    // Ctrl + Scroll Wheel zoom
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;
        const handler = (e) => {
            if (!e.ctrlKey) return;
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            setScale(s => parseFloat((s + delta).toFixed(1)));
        };
        container.addEventListener('wheel', handler, { passive: false });
        return () => container.removeEventListener('wheel', handler);
    }, [setScale]);

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages);
    }

    // Reset state when file changes
    useEffect(() => {
        setNumPages(null);
        setVisiblePage(initialPage);
        setScale(typeof scale === 'number' ? scale : 1.0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fileUrl]);

    const onPageLoadSuccess = useCallback((page) => {
        if (page.pageNumber === initialPage && scrollContainerRef.current) {
            scrollToPage(initialPage);
        }
    }, [initialPage, scrollToPage]);

    // Update input values when state changes via scrolling or buttons
    useEffect(() => {
        setPageInput(visiblePage.toString());
    }, [visiblePage]);

    useEffect(() => {
        setZoomInput(Math.round(scale * 100).toString());
    }, [scale]);

    const handlePageSubmit = (e) => {
        if (e.key === 'Enter') {
            const p = parseInt(pageInput, 10);
            if (!isNaN(p) && p >= 1 && p <= numPages) {
                scrollToPage(p);
            } else {
                setPageInput(visiblePage.toString()); // Revert
            }
        }
    };

    const handleZoomSubmit = (e) => {
        if (e.key === 'Enter') {
            const z = parseInt(zoomInput, 10);
            if (!isNaN(z) && z >= 20 && z <= 500) {
                onScaleChange?.(z / 100);
            } else {
                setZoomInput(Math.round(scale * 100).toString()); // Revert
            }
        }
    };

    useEffect(() => {
        if (!numPages) return;

        if (observerRef.current) {
            observerRef.current.disconnect();
        }

        const options = {
            root: scrollContainerRef.current,
            // Check intersection at roughly the center of the viewport
            rootMargin: '-50% 0px -50% 0px',
            threshold: 0
        };

        const callback = (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const pageNum = parseInt(entry.target.id.replace('pdf-page-', ''), 10);
                    if (!isNaN(pageNum)) {
                        setVisiblePage(pageNum);
                    }
                }
            });
        };

        observerRef.current = new IntersectionObserver(callback, options);

        // We use a small timeout to ensure DOM nodes are ready
        setTimeout(() => {
            for (let i = 1; i <= numPages; i++) {
                const el = document.getElementById(`pdf-page-${i}`);
                if (el) observerRef.current.observe(el);
            }
        }, 100);

        return () => {
            if (observerRef.current) observerRef.current.disconnect();
        };
    }, [numPages]);

    return (
        <div className="flex flex-col h-full w-full relative overflow-hidden bg-gray-200">
            <div className="flex-1 overflow-y-auto w-full flex flex-col items-center p-4 custom-scrollbar" ref={scrollContainerRef}>
                <Document
                    file={fileUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-20">
                            <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                            <p className="text-sm font-medium text-gray-500">Loading PDF...</p>
                        </div>
                    }
                    error={
                        <div className="absolute inset-0 flex items-center justify-center z-20">
                            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200 shadow-sm flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                Failed to load PDF
                            </div>
                        </div>
                    }
                >
                    {numPages && Array.from(new Array(numPages), (el, index) => (
                        <div key={`page_${index + 1}`} id={`pdf-page-${index + 1}`} className="mb-4 shadow-md bg-white">
                            <Page 
                                pageNumber={index + 1} 
                                width={700 * scale} 
                                onLoadSuccess={onPageLoadSuccess}
                                loading={
                                    <div className="animate-pulse bg-gray-100 flex items-center justify-center" style={{ width: `${700 * scale}px`, height: `${900 * scale}px` }}>
                                        <div className="flex flex-col items-center gap-2 text-gray-300">
                                            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                            <span className="text-xs">Page {index + 1}</span>
                                        </div>
                                    </div>
                                }
                            />
                        </div>
                    ))}
                </Document>
            </div>
            
            {numPages && (
                <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-gray-800/80 text-white pl-3 text-sm font-medium shadow-md backdrop-blur-sm z-10 transition-opacity flex items-center border border-gray-700 overflow-hidden" style={{ borderRadius: '20px' }}>
                    <span className="text-gray-300 mr-2 text-xs uppercase tracking-wider">Page</span>
                    <input 
                        type="text" 
                        value={pageInput}
                        onChange={(e) => setPageInput(e.target.value)}
                        onKeyDown={handlePageSubmit}
                        onBlur={() => setPageInput(visiblePage.toString())}
                        className="w-8 text-center bg-transparent border-none focus:outline-none focus:bg-gray-700/50 py-1.5 transition-colors font-semibold"
                        title="Type page number and press Enter"
                    />
                    <span className="text-gray-400 mx-1">/</span>
                    <span className="pr-4 py-1.5">{numPages}</span>
                </div>
            )}
        </div>
    );
}
