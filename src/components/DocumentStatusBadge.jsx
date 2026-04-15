import Badge from './ui/Badge';

export default function DocumentStatusBadge({ status }) {
    const config = {
        pending: { label: 'Pending', variant: 'default' },
        processing: { label: 'Processing', variant: 'primary', spinner: true },
        completed: { label: 'Completed', variant: 'success' },
        failed: { label: 'Failed', variant: 'error' },
    };
    const { label, variant, spinner } = config[status] || config.pending;

    return (
        <Badge variant={variant} showSpinner={spinner}>
            {label}
        </Badge>
    );
}
