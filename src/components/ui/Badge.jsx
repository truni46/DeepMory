// src/components/ui/Badge.jsx
import React from 'react';

const VARIANTS = {
    default: 'bg-gray-100 text-gray-600',
    primary: 'bg-blue-100 text-blue-600',
    success: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-600',
    warning: 'bg-yellow-100 text-yellow-700'
};

export default function Badge({ 
    children, 
    variant = 'default', 
    showSpinner = false, 
    className = '' 
}) {
    const baseClass = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium';
    const variantClass = VARIANTS[variant] || VARIANTS.default;

    return (
        <span className={`${baseClass} ${variantClass} ${className}`}>
            {showSpinner && (
                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin flex-shrink-0" />
            )}
            {children}
        </span>
    );
}
