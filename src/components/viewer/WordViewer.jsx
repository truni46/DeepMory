import { useState, useEffect, useRef, useCallback } from 'react';
import { renderAsync } from 'docx-preview';
import { useDelayedSpinner } from '../../hooks/useDelayedSpinner';

export default function WordViewer({ fileUrl, initialPage = 1, scale = 1.0, onScaleChange }) {
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [numPages, setNumPages] = useState(null);
    const [visiblePage, setVisiblePage] = useState(initialPage);
    const [pageInput, setPageInput] = useState('');

    const containerRef = useRef(null);
    const wrapperRef = useRef(null);
    const scrollRef = useRef(null);
    const observerRef = useRef(null);

    const showSpinner = useDelayedSpinner(loading && !error);

    const scrollToPage = useCallback((pageNum) => {
        const el = document.getElementById(`docx-page-${pageNum}`);
        if (el) el.scrollIntoView({ behavior: 'auto', block: 'start' });
    }, []);

    // Render docx into container
    useEffect(() => {
        if (!fileUrl || !containerRef.current) return;
        let cancelled = false;

        setLoading(true);
        setError(null);
        setNumPages(null);
        containerRef.current.innerHTML = '';

        fetch(fileUrl)
            .then(res => res.arrayBuffer())
            .then(buf => {
                if (cancelled || !containerRef.current) return;
                return renderAsync(buf, containerRef.current, null, {
                    inWrapper: true,
                    breakPages: true,
                    ignoreLastRenderedPageBreak: false,
                    experimental: true,
                    useBase64URL: true,
                    className: 'docx',
                });
            })
            .then(() => {
                if (cancelled || !containerRef.current) return;
                const sections = containerRef.current.querySelectorAll('section.docx');
                sections.forEach((sec, idx) => {
                    sec.id = `docx-page-${idx + 1}`;
                });
                setNumPages(sections.length || 1);
                setLoading(false);
                setTimeout(() => scrollToPage(initialPage), 100);
            })
            .catch(err => {
                if (cancelled) return;
                console.error('WordViewer render failed:', err);
                setError('Could not render Word document.');
                setLoading(false);
            });

        return () => { cancelled = true; };
    }, [fileUrl, initialPage, scrollToPage]);

    // Apply zoom
    useEffect(() => {
        const wrap = wrapperRef.current;
        if (!wrap) return;
        wrap.style.transform = `scale(${scale})`;
        wrap.style.transformOrigin = 'top center';
        wrap.style.transition = 'transform 0.1s';
    }, [scale, numPages]);

    // Ctrl+wheel zoom
    useEffect(() => {
        const container = scrollRef.current;
        if (!container || !onScaleChange) return;
        const handler = (e) => {
            if (!e.ctrlKey) return;
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            const next = parseFloat((scale + delta).toFixed(1));
            const clamped = Math.min(3.0, Math.max(0.2, next));
            onScaleChange(clamped);
        };
        container.addEventListener('wheel', handler, { passive: false });
        return () => container.removeEventListener('wheel', handler);
    }, [scale, onScaleChange]);

    // Observe visible page
    useEffect(() => {
        if (!numPages || !scrollRef.current) return;
        if (observerRef.current) observerRef.current.disconnect();

        const obs = new IntersectionObserver(
            (entries) => {
                let latest = null;
                entries.forEach(e => {
                    if (e.isIntersecting) {
                        const p = parseInt(e.target.id.replace('docx-page-', ''), 10);
                        if (!isNaN(p)) latest = p;
                    }
                });
                if (latest !== null) setVisiblePage(latest);
            },
            { root: scrollRef.current, rootMargin: '-45% 0px -45% 0px', threshold: 0 },
        );
        observerRef.current = obs;

        setTimeout(() => {
            for (let i = 1; i <= numPages; i++) {
                const el = document.getElementById(`docx-page-${i}`);
                if (el) obs.observe(el);
            }
        }, 100);

        return () => obs.disconnect();
    }, [numPages]);

    useEffect(() => {
        setPageInput(visiblePage.toString());
    }, [visiblePage]);

    const handlePageSubmit = (e) => {
        if (e.key === 'Enter') {
            const p = parseInt(pageInput, 10);
            if (!isNaN(p) && p >= 1 && p <= numPages) {
                scrollToPage(p);
            } else {
                setPageInput(visiblePage.toString());
            }
        }
    };

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm border border-red-200 flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full w-full relative overflow-hidden bg-gray-200">
            <div ref={scrollRef} className="flex-1 overflow-auto w-full flex flex-col items-center p-4 custom-scrollbar">
                {loading && showSpinner && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-20 bg-gray-100/40">
                        <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                        <p className="text-sm font-medium text-gray-500">Loading document...</p>
                    </div>
                )}
                <div ref={wrapperRef} className="docx-zoom-wrapper">
                    <div ref={containerRef} />
                </div>
            </div>

            {numPages > 0 && (
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
