import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import ConversationList from './ConversationList';
import logo from '../assets/logo.png';

export default function Sidebar({
    conversations = [],
    activeConversationId,
    onNewChat = () => { },
    onSelectConversation = () => { },
    onDeleteConversation = () => { },
    onOpenSettings = () => { },
    user,
    deletingId
}) {
    const [isExpanded, setIsExpanded] = useState(true);
    const location = useLocation();
    const isDocumentsPage = location.pathname === '/documents';

    return (
        <div className={`${isExpanded ? 'w-64' : 'w-16'} bg-sidebar border-r border-border flex flex-col h-full transition-all duration-300`}>
            {/* Header */}
            <div className="p-3 border-b border-border flex items-center justify-between">
                {isExpanded ? (
                    <>
                        <div className="flex items-center space-x-2">
                            <img src={logo} alt="Logo" className="w-8 h-8 object-contain" />
                            <span className="font-semibold text-text-primary">AI-Tutor</span>
                        </div>
                        <button
                            onClick={() => setIsExpanded(false)}
                            className="p-1.5 hover:bg-bg-tertiary rounded-lg transition-colors"
                        >
                            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                            </svg>
                        </button>
                    </>
                ) : (
                    <button
                        onClick={() => setIsExpanded(true)}
                        className="w-full p-1.5 hover:bg-bg-tertiary rounded-lg transition-colors flex justify-center"
                    >
                        <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Sidebar Content */}
            <div className="flex-1 flex flex-col">
                {isExpanded ? (
                    <>
                        {/* New Chat Button */}
                        <div className="p-3">
                            <button
                                onClick={onNewChat}
                                className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg border border-border hover:bg-bg-tertiary transition-colors text-text-primary"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                </svg>
                                <span className="font-medium">New chat</span>
                            </button>
                        </div>

                        {/* Navigation Items */}
                        <nav className="px-3 space-y-1">
                            <Link
                                to="/documents"
                                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors ${isDocumentsPage
                                    ? 'bg-bg-tertiary text-text-primary'
                                    : 'hover:bg-bg-tertiary text-text-secondary'
                                    }`}
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                <span className="text-sm">Documents</span>
                            </Link>
                            <button className="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-bg-tertiary transition-colors text-text-secondary">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                </svg>
                                <span className="text-sm">Library</span>
                            </button>
                        </nav>

                        {/* Chats Section */}
                        <div className="flex-1 mt-4">
                            <div className="px-3 mb-2">
                                <button className="w-full flex items-center justify-between text-text-secondary hover:text-text-primary transition-colors">
                                    <span className="text-xs font-semibold uppercase tracking-wide">Chats</span>
                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                </button>
                            </div>
                            <ConversationList
                                conversations={conversations}
                                activeId={isDocumentsPage ? null : activeConversationId}
                                onSelect={onSelectConversation}
                                onDelete={onDeleteConversation}
                                deletingId={deletingId}
                            />
                        </div>
                    </>
                ) : (
                    /* Icon-only mode */
                    <div className="flex flex-col items-center space-y-2 p-2 mt-2">
                        <button
                            onClick={onNewChat}
                            className="p-2.5 rounded-lg hover:bg-bg-tertiary transition-colors"
                            title="New chat"
                        >
                            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                            </svg>
                        </button>
                        <Link
                            to="/documents"
                            className={`p-2.5 rounded-lg transition-colors ${isDocumentsPage
                                ? 'bg-bg-tertiary text-text-primary'
                                : 'hover:bg-bg-tertiary text-text-secondary'
                                }`}
                            title="Documents"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        </Link>
                        <button className="p-2.5 rounded-lg hover:bg-bg-tertiary transition-colors" title="Library">
                            <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                            </svg>
                        </button>
                    </div>
                )}
            </div>

            {/* User Profile - Bottom */}
            {isExpanded && (
                <div className="p-3 border-t border-border">
                    <button
                        onClick={onOpenSettings}
                        className="w-full flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-bg-tertiary transition-colors"
                    >
                        <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-xs font-semibold">
                            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : (user?.username?.charAt(0).toUpperCase() || 'U')}
                        </div>
                        <span className="text-sm text-text-primary font-medium truncate">
                            {user?.full_name || user?.username || 'User'}
                        </span>
                    </button>
                </div>
            )}
        </div>
    );
}
