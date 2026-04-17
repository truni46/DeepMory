import { useState, useEffect } from 'react';

/**
 * Shows spinner only if loading takes longer than `delay` ms.
 * Prevents flash of loading state for fast operations.
 *
 * @param {boolean} isLoading - whether content is loading
 * @param {number} delay - ms to wait before showing spinner (default 300)
 * @returns {boolean} showSpinner
 */
export function useDelayedSpinner(isLoading, delay = 200) {
    const [showSpinner, setShowSpinner] = useState(false);

    useEffect(() => {
        if (!isLoading) {
            setShowSpinner(false);
            return;
        }
        const timer = setTimeout(() => setShowSpinner(true), delay);
        return () => clearTimeout(timer);
    }, [isLoading, delay]);

    return showSpinner;
}
