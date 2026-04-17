// src/components/ui/Table.jsx
import React from 'react';

export default function Table({ headers = [], children, className = '' }) {
    return (
        <div className={`overflow-x-auto w-full ${className}`}>
            <table className="w-full text-left border-collapse">
                <thead className="bg-gray-50 text-text-secondary text-xs font-medium uppercase tracking-wide border-b border-border-color">
                    <tr>
                        {headers.map((header, index) => (
                            <th 
                                key={index} 
                                className={`px-6 py-3 whitespace-nowrap ${index === headers.length - 1 ? 'text-right' : ''}`}
                            >
                                {header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-border-color bg-white">
                    {children}
                </tbody>
            </table>
        </div>
    );
}

export function TableRow({ children, className = '', onClick }) {
    return (
        <tr 
            className={`hover:bg-gray-50 transition-colors ${onClick ? 'cursor-pointer' : ''} ${className}`}
            onClick={onClick}
        >
            {children}
        </tr>
    );
}

export function TableCell({ children, className = '', isLast = false }) {
    return (
        <td className={`px-6 py-4 whitespace-nowrap ${isLast ? 'text-right' : ''} ${className}`}>
            {children}
        </td>
    );
}
