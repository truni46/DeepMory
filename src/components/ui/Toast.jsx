import React from 'react';
import { HiCheckCircle, HiExclamationCircle, HiXCircle } from 'react-icons/hi';

const TOAST_CONFIG = {
    success: {
        icon: HiCheckCircle,
        iconClass: 'text-green-500',
    },
    info: {
        icon: HiExclamationCircle,
        iconClass: 'text-blue-500',
    },
    error: {
        icon: HiXCircle,
        iconClass: 'text-red-500',
    },
};

function ToastItem({ toast, onDismiss }) {
    const config = TOAST_CONFIG[toast.type] || TOAST_CONFIG.info;
    const Icon = config.icon;
    const animationClass = toast.isExiting ? 'animate-toast-out' : 'animate-toast-in';

    return (
        <div
            className={`flex items-start gap-2.5 px-3 py-2 bg-white rounded-2xl shadow-lg border border-gray-200 w-fit max-w-[420px] h-fit cursor-pointer ${animationClass}`}
            role="alert"
            onClick={() => onDismiss(toast.id)}
        >
            <Icon className={`w-5 h-5 flex-shrink-0  ${config.iconClass}`} />
            <div className="flex flex-col">
                <p className="text-sm font-semibold text-gray-900 leading-5">{toast.title}</p>
                {toast.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{toast.description}</p>
                )}
            </div>
        </div>
    );
}

export default function ToastContainer({ toasts, onDismiss }) {
    if (!toasts || toasts.length === 0) return null;

    return (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-3 pointer-events-none">
            {toasts.map((toast) => (
                <div key={toast.id} className="pointer-events-auto">
                    <ToastItem toast={toast} onDismiss={onDismiss} />
                </div>
            ))}
        </div>
    );
}
