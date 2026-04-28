import { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';
import { useDelayedSpinner } from '../../hooks/useDelayedSpinner';

export default function ExcelViewer({ fileUrl }) {
    const [sheets, setSheets] = useState(null);
    const [activeSheet, setActiveSheet] = useState(0);
    const [error, setError] = useState(null);
    const showSpinner = useDelayedSpinner(sheets === null && !error);

    useEffect(() => {
        if (!fileUrl) return;
        setSheets(null);
        setError(null);
        setActiveSheet(0);
        fetch(fileUrl)
            .then(res => res.arrayBuffer())
            .then(buf => {
                const workbook = XLSX.read(buf, { type: 'array' });
                const parsed = workbook.SheetNames.map(name => ({
                    name,
                    rows: XLSX.utils.sheet_to_json(workbook.Sheets[name], { header: 1, defval: '' }),
                }));
                setSheets(parsed);
            })
            .catch(() => setError('Could not render Excel file.'));
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

    if (!sheets) {
        return showSpinner ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-500">Loading spreadsheet...</span>
            </div>
        ) : null;
    }

    const currentRows = sheets[activeSheet]?.rows || [];
    const headers = currentRows[0] || [];
    const dataRows = currentRows.slice(1);

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {sheets.length > 1 && (
                <div className="flex gap-1 px-4 pt-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
                    {sheets.map((sheet, i) => (
                        <button key={sheet.name} onClick={() => setActiveSheet(i)}
                            className={`px-3 py-1.5 text-xs rounded-t border-b-2 transition-colors ${
                                i === activeSheet ? 'border-primary text-primary font-medium bg-white' : 'border-transparent text-text-secondary hover:text-primary'
                            }`}>{sheet.name}</button>
                    ))}
                </div>
            )}
            <div className="flex-1 overflow-auto custom-scrollbar">
                <table className="text-xs border-collapse w-max min-w-full">
                    <thead className="sticky top-0 bg-gray-100 z-10">
                        <tr>
                            {headers.map((h, i) => (
                                <th key={i} className="border border-gray-300 px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">{String(h)}</th>
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
