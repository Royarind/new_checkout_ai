import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export const useAuth = () => {
    const navigate = useNavigate();

    const getToken = () => {
        return localStorage.getItem('token');
    };

    const getUser = () => {
        const userStr = localStorage.getItem('user');
        return userStr ? JSON.parse(userStr) : null;
    };

    const isAuthenticated = () => {
        return !!getToken();
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        navigate('/auth');
    };

    const requireAuth = () => {
        if (!isAuthenticated()) {
            navigate('/auth');
            return false;
        }
        return true;
    };

    return {
        getToken,
        getUser,
        isAuthenticated,
        logout,
        requireAuth
    };
};

// HOC for protected routes
export const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const { requireAuth } = useAuth();

    useEffect(() => {
        requireAuth();
    }, []);

    return <>{children}</>;
};

// API helper with auth token
export const apiCall = async (endpoint: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('token');

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {})
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`http://localhost:8000${endpoint}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        // Token expired or invalid
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/auth';
    }

    return response;
};
