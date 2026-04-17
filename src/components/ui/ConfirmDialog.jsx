// src/components/ui/ConfirmDialog.jsx
import { useEffect, useRef } from 'react';
import { HiExclamationTriangle } from 'react-icons/hi2';

export default function ConfirmDialog({
    open,
    title = 'Are you sure?',
    description,
    confirmLabel = 'Delete',
    cancelLabel = 'Cancel',
    onConfirm,
    onCancel,
    variant = 'danger',
}) {
    const dialogRef = useRef(null);

    useEffect(() => {
        if (open) {
            dialogRef.current?.focus();
        }
    }, [open]);

    useEffect(() => {
        if (!open) return;
        const handler = (e) => {
            if (e.key === 'Escape') onCancel();
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [open, onCancel]);

    if (!open) return null;

    const confirmClass = variant === 'danger'
        ? 'bg-red-500 hover:bg-red-600 text-white'
        : 'bg-primary hover:bg-primary/90 text-white';

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
            <div
                ref={dialogRef}
                tabIndex={-1}
                className="relative bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4 animate-toast-in outline-none"
            >
                <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                        <HiExclamationTriangle className="w-5 h-5 text-red-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
                        {description && (
                            <p className="text-sm text-gray-500 mt-1">{description}</p>
                        )}
                    </div>
                </div>
                <div className="flex items-center justify-end gap-2 mt-5">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        onClick={onConfirm}
                        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${confirmClass}`}
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
