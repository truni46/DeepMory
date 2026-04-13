// src/components/ui/WordViewer.jsx
import { useState, useEffect } from 'react';
import mammoth from 'mammoth';

export default function WordViewer({ fileUrl }) {
    const [html, setHtml] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!fileUrl) return;
        fetch(fileUrl)
            .then(res => res.arrayBuffer())
            .then(buf => mammoth.convertToHtml({ arrayBuffer: buf }))
            .then(result => setHtml(result.value))
            .catch(() => setError('Could not render Word document.'));
    }, [fileUrl]);

    if (error) {
        return (
            <div className="flex items-center justify-center h-full text-sm text-red-500">
                {error}
            </div>
        );
    }

    if (!html) {
        return (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
                Loading document...
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-8 bg-white">
            <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: html }}
            />
        </div>
    );
}
