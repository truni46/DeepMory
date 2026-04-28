// src/components/ui/Table.jsx
import React from 'react';

export default function Table({ headers = [], children, className = '' }) {
    return (
        <div className={`overflow-x-auto w-full ${className}`}>
            <table className="w-full text-left border-separate border-spacing-0">
                <thead className="text-text-secondary text-sm font-medium tracking-wide">
                    <tr>
                        {headers.map((header, index) => (
                            <th
                                key={index}
                                className={`py-3 whitespace-nowrap bg-primary text-white border-b border-border-color ${index === 0 && typeof header !== 'string' ? 'w-12 px-3' : 'px-6'} ${index === headers.length - 1 ? 'text-right' : ''} ${index === 0 ? 'rounded-tl-xl' : ''} ${index === headers.length - 1 ? 'rounded-tr-xl' : ''}`}
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
