import React, { useState } from 'react';
import { Play, RotateCcw, Settings } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { automationAPI, chatAPI, configAPI } from '../api/client';
import './AutomationControls.css';

export const AutomationControls: React.FC = () => {
    const [showConfig, setShowConfig] = useState(false);
    const [llmConfig, setLlmConfig] = useState<any>(null);

    const {
        jsonData,
        automationRunning,
        automationStatus,
        setAutomationRunning,
        setAutomationStatus,
        resetChat,
    } = useAppStore();

    const handleStart = async () => {
        if (!jsonData.tasks?.[0]?.url) {
            alert('Please provide a product URL first');
            return;
        }

        setAutomationRunning(true);
        setAutomationStatus('Starting automation...');

        try {
            const result = await automationAPI.start(jsonData);
            setAutomationStatus(
                result.status === 'completed'
                    ? `✅ Success! Final URL: ${result.final_url}`
                    : `❌ Failed: ${result.error}`
            );
        } catch (error) {
            setAutomationStatus(`❌ Error: ${error}`);
        } finally {
            setAutomationRunning(false);
        }
    };

    const handleReset = async () => {
        if (confirm('Are you sure you want to reset? All data will be cleared.')) {
            try {
                await chatAPI.reset();
                resetChat();
                setAutomationStatus(null);
            } catch (error) {
                console.error('Reset error:', error);
            }
        }
    };

    const handleShowConfig = async () => {
        if (!showConfig) {
            try {
                const config = await configAPI.getLLMConfig();
                setLlmConfig(config);
            } catch (error) {
                console.error('Config error:', error);
            }
        }
        setShowConfig(!showConfig);
    };

    return (
        <div className="automation-controls">
            <div className="controls-header">
                <h2>Automation Controls</h2>
            </div>

            <div className="controls-buttons">
                <button
                    className="btn btn-primary control-btn"
                    onClick={handleStart}
                    disabled={automationRunning}
                >
                    <Play size={18} />
                    {automationRunning ? 'Running...' : 'Start Automation'}
                </button>

                <button className="btn btn-secondary control-btn" onClick={handleReset}>
                    <RotateCcw size={18} />
                    Reset
                </button>

                <button className="btn btn-secondary control-btn" onClick={handleShowConfig}>
                    <Settings size={18} />
                    LLM Config
                </button>
            </div>

            {automationStatus && (
                <div className={`status-message ${automationStatus.includes('✅') ? 'status-success' : 'status-error'} fade-in`}>
                    {automationStatus}
                </div>
            )}

            {showConfig && llmConfig && (
                <div className="config-panel fade-in">
                    <h3>LLM Configuration</h3>
                    <div className="config-info">
                        <div className="config-row">
                            <span className="config-label">Provider:</span>
                            <span className="config-value">{llmConfig.provider}</span>
                        </div>
                        <div className="config-row">
                            <span className="config-label">Model:</span>
                            <span className="config-value">{llmConfig.model}</span>
                        </div>
                        {llmConfig.base_url && (
                            <div className="config-row">
                                <span className="config-label">Base URL:</span>
                                <span className="config-value">{llmConfig.base_url}</span>
                            </div>
                        )}
                    </div>
                    <p className="config-note">
                        💡 LLM settings are loaded from the <code>.env</code> file
                    </p>
                </div>
            )}
        </div>
    );
};
