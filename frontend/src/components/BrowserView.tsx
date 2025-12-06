import React, { useEffect, useState } from 'react';
import { Monitor, RefreshCw } from 'lucide-react';
import './BrowserView.css';

interface Screenshot {
    screenshot: string | null;
    timestamp: string | null;
}

export const BrowserView: React.FC = () => {
    const [screenshot, setScreenshot] = useState<Screenshot>({ screenshot: null, timestamp: null });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchScreenshot = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const response = await fetch('http://localhost:8000/api/screenshots/latest');

            if (!response.ok) {
                throw new Error('Failed to fetch screenshot');
            }

            const data = await response.json();
            setScreenshot(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            console.error('Screenshot fetch error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        // Initial fetch
        fetchScreenshot();

        // Poll every 1 second
        const interval = setInterval(fetchScreenshot, 1000);

        return () => clearInterval(interval);
    }, []);

    return (
        <div className="browser-view">
            <div className="browser-view-header">
                <div className="header-left">
                    <Monitor size={20} />
                    <h3>Live Browser</h3>
                </div>
                <button
                    className="refresh-btn"
                    onClick={fetchScreenshot}
                    disabled={isLoading}
                    title="Refresh screenshot"
                >
                    <RefreshCw size={16} className={isLoading ? 'icon-spin' : ''} />
                </button>
            </div>

            <div className="browser-view-content">
                {error && (
                    <div className="browser-placeholder error">
                        <div className="placeholder-icon">⚠️</div>
                        <div className="placeholder-text">
                            Error loading screenshot
                            <div className="error-message">{error}</div>
                        </div>
                    </div>
                )}

                {!error && !screenshot.screenshot && (
                    <div className="browser-placeholder">
                        <div className="placeholder-icon">🖥️</div>
                        <div className="placeholder-text">
                            Browser will appear here when automation starts
                        </div>
                        <div className="placeholder-hint">
                            Screenshot updates every second
                        </div>
                    </div>
                )}

                {!error && screenshot.screenshot && (
                    <div className="browser-screenshot fade-in">
                        <img
                            src={`data:image/png;base64,${screenshot.screenshot}`}
                            alt="Live Browser"
                            className="screenshot-image"
                        />
                        {screenshot.timestamp && (
                            <div className="screenshot-timestamp">
                                Last updated: {new Date(screenshot.timestamp).toLocaleTimeString()}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};
