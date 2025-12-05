import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Types
export interface ChatMessage {
    message: string;
}

export interface ChatResponse {
    ai_message: string;
    json_data: any;
    state: string;
}

export interface LLMConfig {
    provider: string;
    model: string;
    api_key?: string;
    base_url?: string;
}

export interface AutomationRequest {
    json_data: any;
}

export interface AutomationStatus {
    status: string;
    phase?: string;
    error?: string;
    final_url?: string;
}

// API Functions
export const chatAPI = {
    sendMessage: async (message: string): Promise<ChatResponse> => {
        const response = await api.post<ChatResponse>('/api/chat', { message });
        return response.data;
    },

    getHistory: async () => {
        const response = await api.get('/api/chat/history');
        return response.data;
    },

    reset: async () => {
        const response = await api.post('/api/chat/reset');
        return response.data;
    },
};

export const configAPI = {
    getLLMConfig: async (): Promise<LLMConfig> => {
        const response = await api.get<LLMConfig>('/api/config/llm');
        return response.data;
    },
};

export const dataAPI = {
    getCurrentData: async () => {
        const response = await api.get('/api/data/current');
        return response.data;
    },
};

export const automationAPI = {
    start: async (jsonData: any): Promise<AutomationStatus> => {
        const response = await api.post<AutomationStatus>('/api/automation/start', {
            json_data: jsonData,
        });
        return response.data;
    },
};

// WebSocket connection
export const createWebSocket = (onMessage: (data: any) => void) => {
    const ws = new WebSocket(`ws://localhost:8000/ws/screenshots`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
    };

    return ws;
};
