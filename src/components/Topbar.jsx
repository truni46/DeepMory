export default function Topbar({ title, right }) {
    return (
        <div className="px-6 pt-3 z-20 flex-shrink-0">
            <div className="flex items-center justify-between px-5 py-3 bg-white rounded-full border border-gray-300 shadow-sm">
                <h2 className="font-semibold text text-text-primary">{title}</h2>
                {right && <div className="flex items-center gap-2">{right}</div>}
            </div>
        </div>
    );
}
