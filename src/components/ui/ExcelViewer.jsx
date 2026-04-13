// src/components/ui/ExcelViewer.jsx
import { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';

export default function ExcelViewer({ fileUrl }) {
    const [sheets, setSheets] = useState(null);
    const [activeSheet, setActiveSheet] = useState(0);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!fileUrl) return;
        fetch(fileUrl)
            .then(res => res.arrayBuffer())
            .then(buf => {
                const workbook = XLSX.read(buf, { type: 'array' });
                const parsed = workbook.SheetNames.map(name => ({
                    name,
                    rows: XLSX.utils.sheet_to_json(workbook.Sheets[name], {
                        header: 1,
                        defval: '',
                    }),
                }));
                setSheets(parsed);
            })
            .catch(() => setError('Could not render Excel file.'));
    }, [fileUrl]);

    if (error) {
        return (
            <div className="flex items-center justify-center h-full text-sm text-red-500">
                {error}
            </div>
        );
    }

    if (!sheets) {
        return (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
                Loading spreadsheet...
            </div>
        );
    }

    const currentRows = sheets[activeSheet]?.rows || [];
    const headers = currentRows[0] || [];
    const dataRows = currentRows.slice(1);

    return (
        <div className="flex flex-col h-full overflow-hidden">
            {sheets.length > 1 && (
                <div className="flex gap-1 px-4 pt-3 border-b border-gray-200 bg-gray-50 flex-shrink-0">
                    {sheets.map((sheet, i) => (
                        <button
                            key={sheet.name}
                            onClick={() => setActiveSheet(i)}
                            className={`px-3 py-1.5 text-xs rounded-t border-b-2 transition-colors ${
                                i === activeSheet
                                    ? 'border-primary text-primary font-medium bg-white'
                                    : 'border-transparent text-text-secondary hover:text-primary'
                            }`}
                        >
                            {sheet.name}
                        </button>
                    ))}
                </div>
            )}

            <div className="flex-1 overflow-auto">
                <table className="text-xs border-collapse w-max min-w-full">
                    <thead className="sticky top-0 bg-gray-100 z-10">
                        <tr>
                            {headers.map((h, i) => (
                                <th
                                    key={i}
                                    className="border border-gray-300 px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap"
                                >
                                    {String(h)}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {dataRows.map((row, ri) => (
                            <tr key={ri} className="hover:bg-blue-50">
                                {headers.map((_, ci) => (
                                    <td
                                        key={ci}
                                        className="border border-gray-200 px-3 py-1.5 text-gray-700 whitespace-nowrap"
                                    >
                                        {String(row[ci] ?? '')}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
