import { useState } from 'react';
import DocumentUploadZone from '../components/DocumentUploadZone';
import DocumentTable from '../components/DocumentTable';

export default function DocumentsPage() {
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden">
            <header className="px-6 py-4 border-b border-border-color bg-white shadow-sm">
                <h1 className="text-2xl font-bold text-primary">My Documents</h1>
            </header>

            <main className="flex-1 overflow-y-auto p-8">
                <div className="max-w-5xl mx-auto space-y-8">
                    <DocumentUploadZone
                        onUploadComplete={() => setRefreshTrigger(t => t + 1)}
                    />
                    <DocumentTable refreshTrigger={refreshTrigger} />
                </div>
            </main>
        </div>
    );
}
