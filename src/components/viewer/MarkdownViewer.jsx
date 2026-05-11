import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { useDelayedSpinner } from '../../hooks/useDelayedSpinner';

export default function MarkdownViewer({ fileUrl }) {
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
            .catch(() => setError('Could not load markdown file.'));
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
                <span className="text-sm text-gray-500">Loading...</span>
            </div>
        ) : null;
    }

    return (
        <div className="h-full overflow-y-auto custom-scrollbar px-8 py-6 bg-white">
            <div className="max-w-3xl mx-auto prose prose-sm prose-gray
                prose-headings:font-bold prose-headings:text-gray-900
                prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg
                prose-p:text-gray-700 prose-p:leading-relaxed
                prose-a:text-blue-600 hover:prose-a:underline
                prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:font-mono
                prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:rounded-lg prose-pre:overflow-x-auto
                prose-blockquote:border-l-4 prose-blockquote:border-blue-300 prose-blockquote:bg-blue-50 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r
                prose-li:text-gray-700 prose-ul:list-disc prose-ol:list-decimal
                prose-table:border-collapse prose-th:bg-gray-100 prose-th:border prose-th:border-gray-300 prose-th:px-3 prose-th:py-2
                prose-td:border prose-td:border-gray-200 prose-td:px-3 prose-td:py-1.5
                max-w-none"
            >
                <ReactMarkdown>{content}</ReactMarkdown>
            </div>
        </div>
    );
}
