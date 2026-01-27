import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ChatLayout() {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-bg-main">
                <div className="text-center">
                    <div className="text-6xl mb-4 animate-bounce">🤖</div>
                    <h2 className="text-xl font-semibold text-primary">Loading...</h2>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return (
        <Outlet />
    );
}
