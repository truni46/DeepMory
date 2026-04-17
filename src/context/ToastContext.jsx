import { createContext, useContext, useState, useCallback, useRef } from 'react';

const ToastContext = createContext(null);
const MAX_TOASTS = 5;
const DEFAULT_DURATION = 2000;
const EXIT_ANIMATION_MS = 200;

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);
    const timersRef = useRef({});

    const dismiss = useCallback((id) => {
        setToasts((prev) =>
            prev.map((t) => (t.id === id ? { ...t, isExiting: true } : t))
        );
        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
        }, EXIT_ANIMATION_MS);

        if (timersRef.current[id]) {
            clearTimeout(timersRef.current[id]);
            delete timersRef.current[id];
        }
    }, []);

    const showToast = useCallback(({ type = 'info', title, description, duration = DEFAULT_DURATION }) => {
        const id = Date.now() + '-' + Math.random().toString(36).slice(2, 9);
        const newToast = { id, type, title, description, isExiting: false };

        setToasts((prev) => {
            const next = [...prev, newToast];
            if (next.length > MAX_TOASTS) {
                const oldest = next[0];
                dismiss(oldest.id);
                return next.slice(1);
            }
            return next;
        });

        timersRef.current[id] = setTimeout(() => {
            dismiss(id);
            delete timersRef.current[id];
        }, duration);

        return id;
    }, [dismiss]);

    const success = useCallback((title, description) => {
        return showToast({ type: 'success', title, description });
    }, [showToast]);

    const info = useCallback((title, description) => {
        return showToast({ type: 'info', title, description });
    }, [showToast]);

    const error = useCallback((title, description) => {
        return showToast({ type: 'error', title, description });
    }, [showToast]);

    return (
        <ToastContext.Provider value={{ toasts, showToast, success, info, error, dismiss }}>
            {children}
        </ToastContext.Provider>
    );
};

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};
