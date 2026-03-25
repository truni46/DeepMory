import apiService from './apiService';

class MemoryService {
    async getMemories() {
        return apiService.get('/memory');
    }

    async updateMemory(memoryId, content) {
        return apiService.patch(`/memory/${memoryId}`, { content });
    }

    async deleteMemory(memoryId) {
        return apiService.delete(`/memory/${memoryId}`);
    }

    async getMemorySettings() {
        return apiService.get('/memory/settings');
    }

    async updateMemorySettings(settings) {
        return apiService.put('/memory/settings', settings);
    }
}

export default new MemoryService();
