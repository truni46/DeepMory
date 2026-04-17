import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import LoginPage from './pages/LoginPage';
import DocumentsPage from './pages/DocumentsPage';
import ChatPage from './pages/ChatPage';
import SettingsPage from './pages/SettingsPage';
import ChatLayout from './layouts/ChatLayout';

function App() {
    return (
        <Router>
            <ToastProvider>
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />

                    {/* Protected Routes */}
                    <Route element={<ChatLayout />}>
                        <Route path="/" element={<ChatPage />} />
                        <Route path="/c/:conversationId" element={<ChatPage />} />
                        <Route path="/documents" element={<DocumentsPage />} />
                        <Route path="/settings" element={<SettingsPage />} />
                    </Route>

                    {/* Catch all */}
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </AuthProvider>
            </ToastProvider>
        </Router>
    );
}

export default App;
