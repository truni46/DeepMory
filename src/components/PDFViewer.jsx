// src/components/ui/PDFViewer.jsx
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

const PAGE_BUFFER = 3;
const PAGE_HEIGHT_ESTIMATE = 900;
const DEBOUNCE_MS = 300;

function PagePlaceholder({ width, height, pageNumber }) {
    return (
        <div
            className="flex items-center justify-center bg-white"
            style={{ width: `${width}px`, height: `${height}px` }}
        >
            <div className="flex flex-col items-center gap-2 text-gray-300">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="text-xs">Page {pageNumber}</span>
            </div>
        </div>
    );
}

export default function PDFViewer({ fileUrl, initialPage = 1, scale = 1.0, onScaleChange }) {
    const [numPages, setNumPages] = useState(null);
    const [visiblePage, setVisiblePage] = useState(initialPage);
    const [pageInput, setPageInput] = useState('');
    const [zoomInput, setZoomInput] = useState(Math.round(scale * 100).toString());
    const [renderRange, setRenderRange] = useState({ start: 1, end: 1 + PAGE_BUFFER * 2 });
    const scrollContainerRef = useRef(null);
    const observerRef = useRef(null);
    const pageHeightsRef = useRef({});
    const debounceTimerRef = useRef(null);
    const pendingPageRef = useRef(null);

    const scrollToPage = useCallback((pageNum) => {
        const pageElement = document.getElementById(`pdf-page-${pageNum}`);
        if (pageElement) {
            pageElement.scrollIntoView({ behavior: 'auto', block: 'start' });
        }
    }, []);

    useEffect(() => {
        setZoomInput(Math.round(scale * 100).toString());
    }, [scale]);

    const setScale = useCallback((updater) => {
        if (!onScaleChange) return;
        const next = typeof updater === 'function' ? updater(scale) : updater;
        const clamped = Math.min(3.0, Math.max(0.2, parseFloat(next.toFixed(1))));
        onScaleChange(clamped);
    }, [onScaleChange, scale]);

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

    const updateRenderRangeDebounced = useCallback((pageNum, total) => {
        pendingPageRef.current = pageNum;
        if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = setTimeout(() => {
            const p = pendingPageRef.current;
            const newStart = Math.max(1, p - PAGE_BUFFER);
            const newEnd = Math.min(total, p + PAGE_BUFFER);
            setRenderRange(prev => {
                if (newStart === prev.start && newEnd === prev.end) return prev;
                return { start: newStart, end: newEnd };
            });
            debounceTimerRef.current = null;
        }, DEBOUNCE_MS);
    }, []);

    function onDocumentLoadSuccess({ numPages: total }) {
        setNumPages(total);
        const start = Math.max(1, initialPage - PAGE_BUFFER);
        const end = Math.min(total, initialPage + PAGE_BUFFER);
        setRenderRange({ start, end });
    }

    useEffect(() => {
        setNumPages(null);
        setVisiblePage(initialPage);
        pageHeightsRef.current = {};
    }, [fileUrl, initialPage]);

    useEffect(() => {
        return () => {
            if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
        };
    }, []);

    const onPageLoadSuccess = useCallback((page) => {
        pageHeightsRef.current[page.pageNumber] = page.height * (700 * scale / page.width);
        if (page.pageNumber === initialPage && scrollContainerRef.current) {
            scrollToPage(initialPage);
        }
    }, [initialPage, scrollToPage, scale]);

    useEffect(() => {
        setPageInput(visiblePage.toString());
    }, [visiblePage]);

    const handlePageSubmit = (e) => {
        if (e.key === 'Enter') {
            const p = parseInt(pageInput, 10);
            if (!isNaN(p) && p >= 1 && p <= numPages) {
                if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
                const start = Math.max(1, p - PAGE_BUFFER);
                const end = Math.min(numPages, p + PAGE_BUFFER);
                setRenderRange({ start, end });
                setTimeout(() => scrollToPage(p), 100);
            } else {
                setPageInput(visiblePage.toString());
            }
        }
    };

    const handleZoomSubmit = (e) => {
        if (e.key === 'Enter') {
            const z = parseInt(zoomInput, 10);
            if (!isNaN(z) && z >= 20 && z <= 500) {
                onScaleChange?.(z / 100);
            } else {
                setZoomInput(Math.round(scale * 100).toString());
            }
        }
    };

    useEffect(() => {
        if (!numPages) return;

        if (observerRef.current) {
            observerRef.current.disconnect();
        }

        const visibilityObserver = new IntersectionObserver(
            (entries) => {
                let latestPage = null;
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const pageNum = parseInt(entry.target.id.replace('pdf-page-', ''), 10);
                        if (!isNaN(pageNum)) {
                            latestPage = pageNum;
                        }
                    }
                });
                if (latestPage !== null) {
                    setVisiblePage(latestPage);
                    updateRenderRangeDebounced(latestPage, numPages);
                }
            },
            {
                root: scrollContainerRef.current,
                rootMargin: '-50% 0px -50% 0px',
                threshold: 0,
            },
        );

        observerRef.current = visibilityObserver;

        setTimeout(() => {
            for (let i = 1; i <= numPages; i++) {
                const el = document.getElementById(`pdf-page-${i}`);
                if (el) visibilityObserver.observe(el);
            }
        }, 100);

        return () => {
            if (observerRef.current) observerRef.current.disconnect();
        };
    }, [numPages, updateRenderRangeDebounced]);

    const pageWidth = 700 * scale;

    const shouldRenderPage = useCallback((pageNum) => {
        return pageNum >= renderRange.start && pageNum <= renderRange.end;
    }, [renderRange]);

    const getPageHeight = useCallback((pageNum) => {
        return pageHeightsRef.current[pageNum] || PAGE_HEIGHT_ESTIMATE * scale;
    }, [scale]);

    const pages = useMemo(() => {
        if (!numPages) return null;
        return Array.from({ length: numPages }, (_, index) => {
            const pageNum = index + 1;
            const render = shouldRenderPage(pageNum);
            return (
                <div
                    key={`page_${pageNum}`}
                    id={`pdf-page-${pageNum}`}
                    className="mb-4 shadow-md bg-white"
                    style={!render ? { width: `${pageWidth}px`, height: `${getPageHeight(pageNum)}px` } : undefined}
                >
                    {render ? (
                        <Page
                            pageNumber={pageNum}
                            width={pageWidth}
                            onLoadSuccess={onPageLoadSuccess}
                            loading={
                                <PagePlaceholder width={pageWidth} height={getPageHeight(pageNum)} pageNumber={pageNum} />
                            }
                        />
                    ) : (
                        <PagePlaceholder width={pageWidth} height={getPageHeight(pageNum)} pageNumber={pageNum} />
                    )}
                </div>
            );
        });
    }, [numPages, pageWidth, shouldRenderPage, getPageHeight, onPageLoadSuccess]);

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
                    {pages}
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
