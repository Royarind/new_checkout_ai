import { create } from 'zustand';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface AppState {
    // Chat state
    messages: Message[];
    isLoading: boolean;

    // JSON data being built
    jsonData: any;
    currentState: string;
    detectedVariants: any;

    // Automation state
    automationRunning: boolean;
    automationStatus: string | null;

    // Actions
    addMessage: (message: Message) => void;
    setLoading: (loading: boolean) => void;
    updateJsonData: (data: any) => void;
    updateState: (state: string) => void;
    setAutomationRunning: (running: boolean) => void;
    setAutomationStatus: (status: string | null) => void;
    resetChat: () => void;
}

export const useAppStore = create<AppState>((set) => ({
    // Initial state
    messages: [],
    isLoading: false,
    jsonData: { tasks: [{}] },
    currentState: 'NEED_URL',
    detectedVariants: {},
    automationRunning: false,
    automationStatus: null,

    // Actions
    addMessage: (message) =>
        set((state) => ({
            messages: [...state.messages, message],
        })),

    setLoading: (loading) =>
        set({ isLoading: loading }),

    updateJsonData: (data) =>
        set({ jsonData: data }),

    updateState: (state) =>
        set({ currentState: state }),

    setAutomationRunning: (running) =>
        set({ automationRunning: running }),

    setAutomationStatus: (status) =>
        set({ automationStatus: status }),

    resetChat: () =>
        set({
            messages: [],
            jsonData: { tasks: [{}] },
            currentState: 'NEED_URL',
            detectedVariants: {},
            automationStatus: null,
        }),
}));
