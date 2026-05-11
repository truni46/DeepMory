import { useState } from 'react';
import DocumentUploadZone from '../components/document/DocumentUploadZone';
import DocumentTable from '../components/document/DocumentTable';
import Topbar from '../components/Topbar';

export default function DocumentsPage() {
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden">
            <Topbar title="Documents" />
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
