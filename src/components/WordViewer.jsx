// src/components/ui/WordViewer.jsx
import { useState, useEffect } from 'react';
import mammoth from 'mammoth';
import { useDelayedSpinner } from '../hooks/useDelayedSpinner';

export default function WordViewer({ fileUrl }) {
    const [html, setHtml] = useState(null);
    const [error, setError] = useState(null);
    const showSpinner = useDelayedSpinner(html === null && !error);

    useEffect(() => {
        if (!fileUrl) return;
        setHtml(null);
        setError(null);
        fetch(fileUrl)
            .then(res => res.arrayBuffer())
            .then(buf => mammoth.convertToHtml({ arrayBuffer: buf }))
            .then(result => setHtml(result.value))
            .catch(() => setError('Could not render Word document.'));
    }, [fileUrl]);

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

    if (!html) {
        return showSpinner ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-500">Loading document...</span>
            </div>
        ) : null;
    }

    return (
        <div className="h-full overflow-y-auto p-8 bg-white custom-scrollbar">
            <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: html }} />
        </div>
    );
}
