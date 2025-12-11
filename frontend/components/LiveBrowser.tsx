"use client";

import { useEffect, useState } from "react";

export default function LiveBrowser() {
    const [screenshot, setScreenshot] = useState<string | null>(null);
    const [isLocked, setIsLocked] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [lastUpdate, setLastUpdate] = useState<number>(0);

    useEffect(() => {
        let ws: WebSocket | null = null;
        let reconnectTimeout: NodeJS.Timeout;

        const connectToLiveBrowser = () => {
            try {
                ws = new WebSocket("ws://localhost:8000/ws/live-browser");

                ws.onopen = () => {
                    console.log("Live browser WebSocket connected");
                    setIsConnected(true);
                };

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === "screenshot") {
                            setScreenshot(data.image);
                            setLastUpdate(data.timestamp);
                        } else if (data.type === "lock_state") {
                            setIsLocked(data.locked);
                        } else if (data.type === "connected") {
                            setIsLocked(data.locked);
                        }
                    } catch (error) {
                        console.error("Error parsing WebSocket message:", error);
                    }
                };

                ws.onerror = (error) => {
                    console.error("Live browser WebSocket error:", error);
                    setIsConnected(false);
                };

                ws.onclose = () => {
                    console.log("Live browser WebSocket closed");
                    setIsConnected(false);

                    // Auto-reconnect after 3 seconds
                    reconnectTimeout = setTimeout(() => {
                        console.log("Reconnecting to live browser...");
                        connectToLiveBrowser();
                    }, 3000);
                };
            } catch (error) {
                console.error("Failed to connect to live browser:", error);
                setIsConnected(false);
            }
        };

        connectToLiveBrowser();

        return () => {
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
            if (ws) {
                ws.close();
            }
        };
    }, []);

    return (
        <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
            {/* Screenshot Display */}
            {screenshot ? (
                <img
                    src={screenshot}
                    alt="Live Browser"
                    className="w-full h-full object-contain"
                />
            ) : (
                <div className="flex items-center justify-center h-full text-gray-400">
                    <div className="text-center">
                        <div className="text-6xl mb-4">🌐</div>
                        <p className="text-xl">
                            {isConnected
                                ? "Waiting for automation to start..."
                                : "Connecting to live browser..."}
                        </p>
                    </div>
                </div>
            )}

            {/* Connection Status Badge */}
            <div className="absolute top-4 right-4 flex items-center gap-2 bg-black/50 backdrop-blur-sm px-3 py-2 rounded-lg">
                <div
                    className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
                        }`}
                />
                <span className="text-white text-sm font-medium">
                    {isConnected ? "Connected" : "Disconnected"}
                </span>
            </div>

            {/* Animated Wave Overlay (when locked) */}
            {isLocked && (
                <div className="absolute inset-0 pointer-events-none">
                    {/* Fluorescent Orange Animated Wave */}
                    <div className="absolute inset-0 bg-gradient-to-r from-orange-500/30 via-orange-400/30 to-orange-500/30 animate-wave" />

                    {/* Lock Message */}
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="bg-black/70 backdrop-blur-md px-8 py-6 rounded-2xl border-2 border-orange-500 shadow-2xl">
                            <div className="text-center">
                                <div className="text-6xl mb-4 animate-pulse">🔒</div>
                                <h3 className="text-2xl font-bold text-orange-400 mb-2">
                                    Automation Running
                                </h3>
                                <p className="text-gray-300 text-sm">
                                    Browser is locked during automation
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <style jsx>{`
        @keyframes wave {
          0% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
          100% {
            background-position: 0% 50%;
          }
        }

        .animate-wave {
          background-size: 200% 200%;
          animation: wave 3s ease-in-out infinite;
        }
      `}</style>
        </div>
    );
}
