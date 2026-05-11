import ReactMarkdown from 'react-markdown';

export default function ChatMessage({ message, showTimestamp = true, onDocumentClick }) {
    const isUser = message.role === 'user';
    const date = new Date(message.createdAt || message.timestamp);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear().toString();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const timestamp = `${day}/${month}/${year} ${hours}:${minutes}`;

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6 group w-full`}>
            <div className={`flex items-start space-x-3 ${isUser ? 'max-w-[75%]' : 'w-full'}`}>
                <div className="flex flex-col space-y-1 w-full">
                    <div className={`${isUser ? 'bg-primary text-white' : 'bg-transparent w-full'} rounded-3xl rounded-tr px-4 py-3`}>
                        <div className={`prose prose-sm max-w-none break-words ${isUser ? 'text-white prose-invert' : 'text-text-primary'} [&>p]:!text-[14.5px] [&>p]:!leading-loose [&>ul>li]:!text-[14.5px] [&>ul>li]:!leading-loose [&>ol>li]:!text-[14.5px] [&>ol>li]:!leading-loose [&>ul]:!list-disc [&>ul]:!pl-5`}>
                            {isUser ? (
                                <p className="whitespace-pre-wrap !text-[14.5px] !leading-loose">{message.content}</p>
                            ) : (() => {
                                // Helper: extract page range from docref attrs
                                // Supports: page="12", pages="12-20", pageStart="12" pageEnd="20"
                                function extractPages(attrs) {
                                    const page = attrs.match(/\bpage=(['"])(.*?)\1/)?.[2];
                                    const pages = attrs.match(/\bpages=(['"])(.*?)\1/)?.[2];
                                    const pageStart = attrs.match(/\bpageStart=(['"])(.*?)\1/)?.[2];
                                    const pageEnd = attrs.match(/\bpageEnd=(['"])(.*?)\1/)?.[2];

                                    // Parse a "12-20" range string
                                    if (pages) {
                                        const m = pages.match(/^(\d+)(?:-(\d+))?$/);
                                        return m ? { start: m[1], end: m[2] || null } : { start: null, end: null };
                                    }
                                    if (pageStart) return { start: pageStart, end: pageEnd || null };
                                    if (page) return { start: page, end: null };
                                    return { start: null, end: null };
                                }

                                // Build chip label as "<filename> p.<N>" (or range) — ignore inner tag text
                                function buildChipLabel(file, start, end) {
                                    if (!file) return '';
                                    if (start && end) return `${file} p.${start}–${end}`;
                                    if (start) return `${file} p.${start}`;
                                    return file;
                                }

                                // Hide an unclosed trailing <docref ...  fragment that arrives mid-stream
                                // so users never see raw docId / attribute text while the tag is incomplete.
                                let processedContent = message.content?.replace(/<docref\b[^>]*$/i, '');

                                processedContent = processedContent?.replace(/<docref([^>]*?)>(.*?)<\/docref>/gi, (match, attrs /* innerText ignored */) => {
                                    const file = attrs.match(/file=(['"])(.*?)\1/)?.[2] || '';
                                    const docId = attrs.match(/docId=(['"])(.*?)\1/)?.[2] || attrs.match(/\bid=(['"])(.*?)\1/)?.[2];
                                    const { start, end } = extractPages(attrs);

                                    const params = new URLSearchParams();
                                    if (start) params.append('pageStart', start);
                                    if (end)   params.append('pageEnd', end);
                                    if (docId) params.append('docId', docId);
                                    const queryString = params.toString();

                                    const url = `#doc:${encodeURIComponent(file)}${queryString ? `?${queryString}` : ''}`;
                                    return `[${buildChipLabel(file, start, end)}](${url})`;
                                });
                                // Self-closing tag: <docref file="abc.pdf" page="12" />
                                processedContent = processedContent?.replace(/<docref([^>]*?)\/>/gi, (match, attrs) => {
                                    const file = attrs.match(/file=(['"])(.*?)\1/)?.[2] || '';
                                    const docId = attrs.match(/docId=(['"])(.*?)\1/)?.[2] || attrs.match(/\bid=(['"])(.*?)\1/)?.[2];
                                    const { start, end } = extractPages(attrs);

                                    const params = new URLSearchParams();
                                    if (start) params.append('pageStart', start);
                                    if (end)   params.append('pageEnd', end);
                                    if (docId) params.append('docId', docId);
                                    const queryString = params.toString();

                                    const url = `#doc:${encodeURIComponent(file)}${queryString ? `?${queryString}` : ''}`;
                                    return `[${buildChipLabel(file, start, end)}](${url})`;
                                });

                                return (
                                    <ReactMarkdown
                                        components={{
                                            a({ node, className, children, href, ...props }) {
                                                if (href?.startsWith('#doc:')) {
                                                    const rawDoc = href.replace('#doc:', '');
                                                    const [encodedFilename, queryString] = rawDoc.split('?');
                                                    const filename = decodeURIComponent(encodedFilename);
                                                    const ext = filename.split('.').pop().toLowerCase();

                                                    let pageStart = null, pageEnd = null, docId = null;
                                                    if (queryString) {
                                                        const params = new URLSearchParams(queryString);
                                                        pageStart = params.get('pageStart');
                                                        pageEnd   = params.get('pageEnd');
                                                        docId     = params.get('docId');
                                                    }

                                                    // Color scheme by file type
                                                    const styleMap = {
                                                        pdf:  { btn: 'bg-white hover:bg-orange-100 text-orange-800 border-orange-300', icon: 'text-orange-600' },
                                                        docx: { btn: 'bg-white hover:bg-blue-100 text-blue-800 border-blue-300',         icon: 'text-blue-600' },
                                                        doc:  { btn: 'bg-white hover:bg-blue-100 text-blue-800 border-blue-300',         icon: 'text-blue-600' },
                                                        xlsx: { btn: 'bg-white hover:bg-green-100 text-green-800 border-green-300',     icon: 'text-green-600' },
                                                        xls:  { btn: 'bg-white hover:bg-green-100 text-green-800 border-green-300',     icon: 'text-green-600' },
                                                        csv:  { btn: 'bg-white hover:bg-green-100 text-green-800 border-green-300',     icon: 'text-green-600' },
                                                        tsv:  { btn: 'bg-white hover:bg-green-100 text-green-800 border-green-300',     icon: 'text-green-6<PASSWORD>' },
                                                        txt:  { btn: 'bg-white hover:bg-gray-100 text-gray-700 border-gray-300',         icon: 'text-gray-500' },
                                                        md:   { btn: 'bg-white hover:bg-purple-100 text-purple-800 border-purple-300', icon: 'text-purple-600' },
                                                    };
                                                    const style = styleMap[ext] ?? { btn: 'bg-white hover:bg-blue-200 text-blue-800 border-blue-300', icon: 'text-blue-600' };

                                                    return (
                                                        <button
                                                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 mx-1 rounded-md border transition-colors align-middle cursor-pointer text-xs font-medium ${style.btn}`}
                                                            onClick={(e) => { e.preventDefault(); onDocumentClick?.(filename, pageStart, docId, pageEnd); }}
                                                            title={`View document: ${filename}`}
                                                        >
                                                            <svg className={`w-3.5 h-3.5 flex-shrink-0 ${style.icon}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                                            </svg>
                                                            {children}
                                                        </button>
                                                    );
                                                }
                                                return <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline" {...props}>{children}</a>;
                                            },
                                            code({ node, inline, className, children, ...props }) {
                                                const match = /language-(\w+)/.exec(className || '')
                                                return !inline && match ? (
                                                    <div className="rounded-md bg-gray-800 p-2 my-2 overflow-x-auto text-xs text-white">
                                                        <code className={className} {...props}>
                                                            {children}
                                                        </code>
                                                    </div>
                                                ) : (
                                                    <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono text-red-500" {...props}>
                                                        {children}
                                                    </code>
                                                )
                                            }
                                        }}
                                    >
                                        {processedContent}
                                    </ReactMarkdown>
                                );
                            })()}
                        </div >
                    </div >

    {/* Timestamp - show on hover */ }
{
    showTimestamp && (
        <span className="text-xs text-text-muted opacity-0 group-hover:opacity-100 transition-opacity px-4">
            {timestamp}
        </span>
    )
}
                </div >
            </div >
        </div >
    );
}
