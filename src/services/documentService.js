// src/services/documentService.js
import apiService from './apiService';

class DocumentService {
    uploadDocuments(files, onProgress, scope = 'personal', onXhr) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            files.forEach(file => formData.append('files', file));

            const xhr = new XMLHttpRequest();
            const token = localStorage.getItem('accessToken');

            if (onXhr) onXhr(xhr);

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable && onProgress) {
                    onProgress(Math.round((event.loaded / event.total) * 100));
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch {
                        resolve([]);
                    }
                } else {
                    reject(new Error(xhr.responseText || 'Upload failed'));
                }
            };

            xhr.onerror = () => reject(new Error('Network error during upload'));
            xhr.onabort = () => reject(new Error('Upload aborted'));

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';
            xhr.open('POST', `${baseUrl}/knowledge/documents/upload?scope=${scope}`);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            xhr.send(formData);
        });
    }

    async getDocuments(scope = null) {
        const params = scope ? `?scope=${scope}` : '';
        return apiService.get(`/knowledge/documents${params}`);
    }

    async getDocument(documentId) {
        return apiService.get(`/knowledge/documents/${documentId}`);
    }

    async getDocumentFileUrl(documentId) {
        const token = localStorage.getItem('accessToken');
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';
        const response = await fetch(
            `${baseUrl}/knowledge/documents/${documentId}/file`,
            { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok) throw new Error('Failed to fetch file');
        const blob = await response.blob();
        return URL.createObjectURL(blob);
    }

    async deleteDocument(documentId) {
        return apiService.delete(`/knowledge/documents/${documentId}`);
    }
}

export default new DocumentService();
