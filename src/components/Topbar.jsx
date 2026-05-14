export default function Topbar({ title, isNew }) {
    return (
        <div className="flex-shrink-0 px-6 py-1">
            {!isNew && (
                <div className="p-2 pl-0 border-b border-gray-200">
                    <h2 className="font-semibold text-lg text-text-primary inline-block rounded-lg px-4 py-1 transition-all border border-transparent">{title}</h2>
                </div>
            )}
        </div>
    );
}
