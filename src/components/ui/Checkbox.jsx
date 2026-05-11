export default function Checkbox({ checked, onChange, onClick, indeterminate = false, variant = 'default' }) {
    const isHeader = variant === 'header';

    const boxClass = indeterminate
        ? 'bg-primary/20 border-primary'
        : checked
            ? isHeader
                ? 'bg-white border-primary'
                : 'bg-primary border-primary'
            : 'bg-white border-gray-300 hover:border-gray-600';

    return (
        <label className="relative inline-flex items-center cursor-pointer" onClick={onClick}>
            <input
                type="checkbox"
                checked={checked}
                onChange={onChange}
                className="sr-only"
            />
            <div className={`w-4 h-4 rounded flex items-center justify-center border transition-all duration-150 ${boxClass}`}>
                {indeterminate && (
                    <svg className="w-2.5 h-2.5 text-primary" viewBox="0 0 12 12" fill="none">
                        <path d="M2.5 6h7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
                    </svg>
                )}
                {!indeterminate && checked && (
                    <svg className={`w-2.5 h-2.5 ${isHeader ? 'text-primary' : 'text-white'}`} viewBox="0 0 12 12" fill="none">
                        <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                )}
            </div>
        </label>
    );
}
