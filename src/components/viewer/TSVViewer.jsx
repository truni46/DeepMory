import { useState, useEffect } from 'react';
import { useDelayedSpinner } from '../../hooks/useDelayedSpinner';

export default function TSVViewer({ fileUrl }) {
    const [rows, setRows] = useState(null);
    const [error, setError] = useState(null);
    const showSpinner = useDelayedSpinner(rows === null && !error);

    useEffect(() => {
        if (!fileUrl) return;
        setRows(null);
        setError(null);
        fetch(fileUrl)
            .then(res => res.text())
            .then(text => {
                const parsed = text
                    .split('\n')
                    .filter(line => line.trim() !== '')
                    .map(line => line.split('\t'));
                setRows(parsed);
            })
            .catch(() => setError('Could not load TSV file.'));
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

    if (!rows) {
        return showSpinner ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-500">Loading TSV...</span>
            </div>
        ) : null;
    }

    const headers = rows[0] || [];
    const dataRows = rows.slice(1);

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <div className="flex-1 overflow-auto custom-scrollbar">
                <table className="text-xs border-collapse w-max min-w-full">
                    <thead className="sticky top-0 bg-gray-100 z-10">
                        <tr>
                            {headers.map((h, i) => (
                                <th key={i} className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap">{String(h)}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {dataRows.map((row, ri) => (
                            <tr key={ri} className="hover:bg-blue-50">
                                {headers.map((_, ci) => (
                                    <td key={ci} className="border border-gray-200 px-3 py-1.5 text-gray-700 whitespace-nowrap">{String(row[ci] ?? '')}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="flex-shrink-0 px-4 py-2 text-xs text-gray-400 border-t border-gray-200 bg-gray-50">
                {dataRows.length} rows · {headers.length} columns
            </div>
        </div>
    );
}
