// src/components/ui/DocumentStatusBadge.jsx
export default function DocumentStatusBadge({ status }) {
    const config = {
        pending:    { label: 'Pending',    className: 'bg-gray-100 text-gray-600' },
        processing: { label: 'Processing', className: 'bg-blue-100 text-blue-600', spinner: true },
        completed:  { label: 'Completed',  className: 'bg-green-100 text-green-700' },
        failed:     { label: 'Failed',     className: 'bg-red-100 text-red-600' },
    };
    const { label, className, spinner } = config[status] || config.pending;

    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${className}`}>
            {spinner && (
                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
            )}
            {label}
        </span>
    );
}
