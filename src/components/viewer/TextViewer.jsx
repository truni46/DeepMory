import { useState, useEffect } from 'react';
import { useDelayedSpinner } from '../../hooks/useDelayedSpinner';

export default function TextViewer({ fileUrl }) {
    const [content, setContent] = useState(null);
    const [error, setError] = useState(null);
    const showSpinner = useDelayedSpinner(content === null && !error);

    useEffect(() => {
        if (!fileUrl) return;
        setContent(null);
        setError(null);
        fetch(fileUrl)
            .then(res => res.text())
            .then(text => setContent(text))
            .catch(() => setError('Could not load text file.'));
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

    if (content === null) {
        return showSpinner ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-500">Loading file...</span>
            </div>
        ) : null;
    }

    const lines = content.split('\n');

    return (
        <div className="flex h-full overflow-hidden bg-gray-50 font-mono text-sm">
            <div className="select-none text-right text-gray-400 bg-gray-100 border-r border-gray-200 px-3 py-4 overflow-hidden flex-shrink-0" style={{ minWidth: '3.5rem' }}>
                {lines.map((_, i) => <div key={i} className="leading-6">{i + 1}</div>)}
            </div>
            <div className="flex-1 overflow-auto px-4 py-4 custom-scrollbar">
                <pre className="whitespace-pre text-gray-800 leading-6">{content}</pre>
            </div>
        </div>
    );
}
