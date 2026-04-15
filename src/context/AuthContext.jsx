import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/apiService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const navigate = useNavigate();

    const logout = useCallback(() => {
        localStorage.removeItem('accessToken');
        setUser(null);
        setIsAuthenticated(false);
        navigate('/login', { replace: true });
    }, [navigate]);

    // Listen for 401 events from apiService
    useEffect(() => {
        const handleUnauthorized = () => logout();
        window.addEventListener('auth:unauthorized', handleUnauthorized);
        return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
    }, [logout]);

    // Check auth on mount
    useEffect(() => {
        const checkAuth = async () => {
            const token = localStorage.getItem('accessToken');
            if (token) {
                try {
                    // Verify token and get user info
                    const userData = await apiService.get('/auth/me');
                    setUser(userData);
                    setIsAuthenticated(true);
                } catch (error) {
                    console.error('Auth check failed:', error);
                    localStorage.removeItem('accessToken');
                    setUser(null);
                    setIsAuthenticated(false);
                }
            }
            setIsLoading(false);
        };

        checkAuth();
    }, []);

    // Login function
    const login = async (email, password) => {
        try {
            const formData = new URLSearchParams();
            formData.append('username', email); // OAuth2PasswordRequestForm expects username
            formData.append('password', password);

            const response = await apiService.request('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData.toString(),
            });

            const { access_token, user: userData } = response;

            // Save token
            localStorage.setItem('accessToken', access_token);

            setUser(userData);
            setIsAuthenticated(true);
            return true;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    };

    // Register function
    const register = async (email, password, fullName) => {
        try {
            await apiService.post('/auth/register', {
                email,
                password,
                full_name: fullName
            });
            // Auto login after register
            return await login(email, password);
        } catch (error) {
            console.error('Register error:', error);
            throw error;
        }
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
