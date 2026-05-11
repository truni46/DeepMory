import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function UserMenu({ user }) {
    const [isOpen, setIsOpen] = useState(false);
    const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
    const menuRef = useRef(null);
    const navigate = useNavigate();
    const { logout } = useAuth();

    // Close on click outside
    useEffect(() => {
        function handleClickOutside(e) {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setIsOpen(false);
            }
        }
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen]);

    // Close on Escape
    useEffect(() => {
        function handleKey(e) {
            if (e.key === 'Escape') setIsOpen(false);
        }
        if (isOpen) {
            document.addEventListener('keydown', handleKey);
        }
        return () => document.removeEventListener('keydown', handleKey);
    }, [isOpen]);

    const menuItems = [
        {
            label: 'Settings',
            icon: (
                <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            ),
            shortcut: 'Ctrl+,',
            onClick: () => { setIsOpen(false); navigate('/settings'); },
        },
        {
            label: 'Analytics',
            icon: (
                <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
            ),
            onClick: () => { setIsOpen(false); },
        },
        {
            label: 'Language',
            icon: (
                <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
            ),
            hasSubmenu: true,
            onClick: () => { },
        },
        {
            label: 'Get help',
            icon: (
                <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                        d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            ),
            onClick: () => { setIsOpen(false); },
        },
    ];

    const handleLogout = () => {
        setIsOpen(false);
        setShowLogoutConfirm(true);
    };

    return (
        <div className="relative py-1" ref={menuRef}>
            {/* Trigger button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center space-x-3 px-3 py-2 rounded-xl hover:bg-bg-tertiary transition-colors"
            >
                <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-xs font-semibold shrink-0">
                    {user?.fullName?.charAt(0).toUpperCase() || 'U'}
                </div>
                <span className="text-sm text-text-primary font-medium truncate flex-1 text-left">
                    {user?.fullName || 'User'}
                </span>
            </button>

            {/* Dropdown menu — opens upward */}
            {isOpen && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-60 bg-white rounded-xl shadow-lg border border-border py-1.5 z-50 animate-fade-in">
                    {/* User info header */}
                    <div className="px-3.5 py-2.5 border-b border-border">
                        <p className="text-sm font-semibold text-text-primary truncate">{user?.fullName || 'User'}</p>
                        <p className="text-xs text-text-muted truncate">{user?.email || ''}</p>
                    </div>

                    {/* Menu items */}
                    <div className="py-1">
                        {menuItems.map((item) => (
                            <button
                                key={item.label}
                                onClick={item.onClick}
                                className="w-full flex items-center justify-between px-3.5 py-2 hover:bg-bg-tertiary transition-colors group"
                            >
                                <div className="flex items-center space-x-3">
                                    <span className="text-text-secondary group-hover:text-text-primary transition-colors">
                                        {item.icon}
                                    </span>
                                    <span className="text-[13.5px] text-text-primary">{item.label}</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    {item.shortcut && (
                                        <span className="text-[11px] text-text-muted bg-bg-secondary px-1.5 py-0.5 rounded">
                                            {item.shortcut}
                                        </span>
                                    )}
                                    {item.hasSubmenu && (
                                        <svg className="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                        </svg>
                                    )}
                                </div>
                            </button>
                        ))}
                    </div>

                    {/* Logout */}
                    <div className="border-t border-border pt-1">
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center space-x-3 px-3.5 py-2 hover:bg-red-50 transition-colors group"
                        >
                            <svg className="w-[18px] h-[18px] text-text-secondary group-hover:text-red-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8}
                                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                            <span className="text-[13.5px] text-text-primary group-hover:text-red-600 transition-colors">Log out</span>
                        </button>
                    </div>
                </div>
            )}

            {/* Logout Confirmation Modal */}
            {showLogoutConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-40 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
                    <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl border border-border">
                        <div className="flex items-center space-x-3 mb-4 text-red-600">
                            <div className="p-2 bg-red-100 rounded-full">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900">Confirm Logout</h3>
                        </div>
                        <p className="text-text-secondary mb-6">
                            Are you sure you want to log out? You will need to sign in again to access your conversations.
                        </p>
                        <div className="flex space-x-3">
                            <button
                                onClick={() => setShowLogoutConfirm(false)}
                                className="flex-1 px-4 py-2 bg-white border border-border text-text-secondary hover:bg-bg-secondary rounded-lg transition-colors font-medium"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={logout}
                                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium shadow-sm"
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
