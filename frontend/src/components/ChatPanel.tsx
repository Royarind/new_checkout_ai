import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { chatAPI } from '../api/client';
import './ChatPanel.css';

export const ChatPanel: React.FC = () => {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { messages, isLoading, addMessage, setLoading, updateJsonData, updateState } = useAppStore();

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = {
            role: 'user' as const,
            content: input,
            timestamp: new Date(),
        };

        addMessage(userMessage);
        setInput('');
        setLoading(true);

        try {
            const response = await chatAPI.sendMessage(input);

            const aiMessage = {
                role: 'assistant' as const,
                content: response.ai_message,
                timestamp: new Date(),
            };

            addMessage(aiMessage);
            updateJsonData(response.json_data);
            updateState(response.state);
        } catch (error) {
            const errorMessage = {
                role: 'assistant' as const,
                content: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date(),
            };
            addMessage(errorMessage);
            console.error('Chat error:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="chat-panel">
            <div className="chat-header">
                <h2>Chat Assistant</h2>
                <p className="chat-subtitle">Let's build your checkout automation</p>
            </div>

            <div className="messages-container">
                {messages.length === 0 && (
                    <div className="welcome-message">
                        <h3>👋 Welcome to CHKout.ai</h3>
                        <p>I'll help you automate your checkout process. Let's start by getting the product URL.</p>
                        <div className="quick-actions">
                            <button className="quick-action-btn" onClick={() => setInput('I want to buy a product')}>
                                🛍️ Start Shopping
                            </button>
                        </div>
                    </div>
                )}

                {messages.map((message, index) => (
                    <div
                        key={index}
                        className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'} fade-in`}
                    >
                        <div className="message-avatar">
                            {message.role === 'user' ? '👤' : '🤖'}
                        </div>
                        <div className="message-content">
                            <div className="message-text">{message.content}</div>
                            <div className="message-time">
                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="message message-assistant fade-in">
                        <div className="message-avatar">🤖</div>
                        <div className="message-content">
                            <div className="typing-indicator">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
                <input
                    type="text"
                    className="chat-input"
                    placeholder="Type your message..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    disabled={isLoading}
                />
                <button
                    className="send-button"
                    onClick={handleSend}
                    disabled={isLoading || !input.trim()}
                >
                    {isLoading ? (
                        <Loader2 className="icon-spin" size={20} />
                    ) : (
                        <Send size={20} />
                    )}
                </button>
            </div>
        </div>
    );
};
