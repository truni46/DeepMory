import apiService from './apiService';

export const documentService = {
    uploadDocument: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return await apiService.post('/knowledge/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
    },

    getDocuments: async () => {
        return await apiService.get('/knowledge/documents');
    },

    deleteDocument: async (documentId) => {
        return await apiService.delete(`/knowledge/documents/${documentId}`);
    }
};
