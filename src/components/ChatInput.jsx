import { useState, useRef, useEffect, useCallback } from 'react';
import DropdownMenu from './ui/DropdownMenu';

const SLASH_COMMANDS = [
    { id: '/research', label: '/research', description: 'Search and gather information', command: '/research' },
    { id: '/plan', label: '/plan', description: 'Create an execution plan', command: '/plan' },
    { id: '/implement', label: '/implement', description: 'Write code or documents', command: '/implement' },
    { id: '/report', label: '/report', description: 'Generate a summary report', command: '/report' },
    { id: '/run', label: '/run', description: 'Execute the full agent pipeline', command: '/run' },
    { id: '/browser', label: '/browser', description: 'Automate browser actions', command: '/browser' },
];

function getSlashCommand(text) {
    const match = text.match(/^(\/\w+)/);
    if (!match) return null;
    return SLASH_COMMANDS.find(c => c.command === match[1]) ? match[1] : null;
}

export default function ChatInput({ onSend, disabled = false }) {
    const [message, setMessage] = useState('');
    const [showCommands, setShowCommands] = useState(false);
    const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const editorRef = useRef(null);
    const isComposing = useRef(false);

    useEffect(() => {
        if (message.startsWith('/')) {
            const query = message.slice(1).toLowerCase().split(' ')[0];
            const hasSpace = message.includes(' ');
            const exactMatch = SLASH_COMMANDS.some(c => c.command === '/' + query);
            if (hasSpace && exactMatch) {
                setShowCommands(false);
                return;
            }
            const filtered = SLASH_COMMANDS.filter(c =>
                c.command.slice(1).startsWith(query) || c.label.toLowerCase().startsWith(query)
            );
            setFilteredCommands(filtered);
            setShowCommands(filtered.length > 0);
            setSelectedIndex(0);
        } else {
            setShowCommands(false);
        }
    }, [message]);

    const renderHighlighted = useCallback(() => {
        const el = editorRef.current;
        if (!el) return;

        const cmd = getSlashCommand(message);
        if (cmd) {
            const rest = message.slice(cmd.length);
            const html = `<span class="slash-cmd" style="color:#007E6E;font-weight:600;">${cmd}</span>${escapeHtml(rest)}`;
            if (el.innerHTML !== html) {
                const sel = window.getSelection();
                const offset = getCaretOffset(el);
                el.innerHTML = html;
                restoreCaret(el, offset);
            }
        } else {
            const text = el.textContent || '';
            if (text !== message) {
                const offset = getCaretOffset(el);
                el.textContent = message;
                restoreCaret(el, offset);
            }
        }
    }, [message]);

    useEffect(() => {
        renderHighlighted();
    }, [message, renderHighlighted]);

    const selectCommand = (cmd) => {
        const newMsg = cmd.command + ' ';
        setMessage(newMsg);
        setShowCommands(false);
        requestAnimationFrame(() => {
            const el = editorRef.current;
            if (!el) return;
            el.focus();
            const totalLen = newMsg.length;
            restoreCaret(el, totalLen);
        });
    };

    const handleSend = () => {
        if (message.trim() && !disabled) {
            onSend(message.trim());
            setMessage('');
            if (editorRef.current) {
                editorRef.current.textContent = '';
            }
            setShowCommands(false);
        }
    };

    const handleKeyDown = (e) => {
        if (isComposing.current) return;

        if (showCommands) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex(prev => (prev + 1) % filteredCommands.length);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
                return;
            }
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                selectCommand(filteredCommands[selectedIndex]);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                setShowCommands(false);
                return;
            }
            if (e.key === 'Tab') {
                e.preventDefault();
                selectCommand(filteredCommands[selectedIndex]);
                return;
            }
        } else if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleInput = () => {
        const text = editorRef.current?.textContent || '';
        setMessage(text);
    };

    const handlePaste = (e) => {
        e.preventDefault();
        const text = e.clipboardData.getData('text/plain');
        document.execCommand('insertText', false, text);
    };

    return (
        <div className="bg-transparent p-4">
            <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end space-x-2 bg-white border border-border rounded-3xl shadow-lg p-2 transition-shadow hover:shadow-xl">
                    <button
                        className="flex-shrink-0 p-2 hover:bg-bg-secondary rounded-full transition-colors"
                        title="Add documents"
                    >
                        <svg className="w-5 h-5 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                    </button>

                    <div className="flex-1 relative">
                        <DropdownMenu
                            items={filteredCommands}
                            selectedIndex={selectedIndex}
                            visible={showCommands}
                            position="top"
                            onSelect={(item) => selectCommand(item)}
                            onHover={(index) => setSelectedIndex(index)}
                        />

                        <div
                            ref={editorRef}
                            contentEditable={!disabled}
                            onInput={handleInput}
                            onKeyDown={handleKeyDown}
                            onPaste={handlePaste}
                            onCompositionStart={() => { isComposing.current = true; }}
                            onCompositionEnd={() => { isComposing.current = false; handleInput(); }}
                            data-placeholder="Ask a question..."
                            className="chat-editor w-full bg-transparent text-sm md:text-[14.5px] text-text-primary resize-none focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-[200px] overflow-y-auto py-2 ml-1 whitespace-pre-wrap break-words empty:before:content-[attr(data-placeholder)] empty:before:text-text-muted"
                            role="textbox"
                            style={{ minHeight: '24px' }}
                        />
                    </div>

                    <button
                        onClick={handleSend}
                        disabled={!message.trim() || disabled}
                        className={`flex-shrink-0 p-2 rounded-full transition-all duration-200 ${message.trim() && !disabled
                            ? 'bg-primary hover:bg-primary-dark text-white shadow-sm'
                            : 'bg-transparent text-text-muted cursor-not-allowed'
                            }`}
                        title={message.trim() ? "Send message" : "Record audio"}
                    >
                        {message.trim() ? (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                        )}
                    </button>
                </div>

                <div className="mt-3 text-center text-xs md:text-sm text-text-muted font-medium opacity-80">
                    DeepMory can make mistakes, please check the response.
                </div>
            </div>
        </div>
    );
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function getCaretOffset(el) {
    const sel = window.getSelection();
    if (!sel.rangeCount) return 0;
    const range = sel.getRangeAt(0).cloneRange();
    range.selectNodeContents(el);
    range.setEnd(sel.getRangeAt(0).endContainer, sel.getRangeAt(0).endOffset);
    return range.toString().length;
}

function restoreCaret(el, offset) {
    const sel = window.getSelection();
    const range = document.createRange();
    let current = 0;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
        const len = node.textContent.length;
        if (current + len >= offset) {
            range.setStart(node, offset - current);
            range.collapse(true);
            sel.removeAllRanges();
            sel.addRange(range);
            return;
        }
        current += len;
    }
    range.selectNodeContents(el);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
}
