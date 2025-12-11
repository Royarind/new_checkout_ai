"use client";

import LiveBrowser from "@/components/LiveBrowser";
import { Pause, Play, RotateCw, Maximize2, Settings } from "lucide-react";
import { useState } from "react";

export default function LiveBrowserPage() {
    const [isPaused, setIsPaused] = useState(false);
    const [interactionMode, setInteractionMode] = useState(true);
    const [currentStep, setCurrentStep] = useState("Selecting Size");
    const [nextStep, setNextStep] = useState("Add to Cart");

    return (
        <div className="h-screen flex flex-col bg-background">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-surface/50">
                <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-white">Live Browser View</h1>
                    <div className="px-3 py-1 rounded-full bg-success/20 border border-success/50">
                        <span className="text-xs font-medium text-success">ON LIVE</span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button className="p-2 rounded-lg glass hover:bg-white/10 transition-colors">
                        <Settings size={20} className="text-text-secondary" />
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left: Browser Viewport */}
                <div className="flex-1 flex flex-col p-6">
                    {/* Browser Controls */}
                    <div className="mb-4 flex items-center gap-3">
                        <button
                            onClick={() => setIsPaused(!isPaused)}
                            className="p-2 rounded-lg glass hover:bg-white/10 transition-colors"
                            title={isPaused ? "Resume" : "Pause"}
                        >
                            {isPaused ? <Play size={20} className="text-success" /> : <Pause size={20} className="text-text-secondary" />}
                        </button>
                        <button className="p-2 rounded-lg glass hover:bg-white/10 transition-colors" title="Refresh">
                            <RotateCw size={20} className="text-text-secondary" />
                        </button>
                        <button className="p-2 rounded-lg glass hover:bg-white/10 transition-colors" title="Fullscreen">
                            <Maximize2 size={20} className="text-text-secondary" />
                        </button>
                        <div className="flex-1" />
                        <div className="text-sm text-text-secondary">
                            Frame: <span className="text-text-primary font-mono">1280x720</span>
                        </div>
                    </div>

                    {/* Browser Viewport */}
                    <div className="flex-1 glass rounded-xl overflow-hidden">
                        <LiveBrowser />
                    </div>
                </div>

                {/* Right: Control Panels */}
                <div className="w-96 border-l border-white/10 p-6 space-y-4 overflow-y-auto">
                    {/* Interaction Panel */}
                    <div className="glass rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-text-primary mb-4">Interaction Panel</h3>

                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-secondary">Interaction Mode</span>
                                <button
                                    onClick={() => setInteractionMode(!interactionMode)}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${interactionMode ? 'bg-success' : 'bg-surface'
                                        }`}
                                >
                                    <span
                                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${interactionMode ? 'translate-x-6' : 'translate-x-1'
                                            }`}
                                    />
                                </button>
                            </div>

                            <div>
                                <label className="text-sm text-text-secondary mb-2 block">Click coordinates</label>
                                <input
                                    type="text"
                                    value="(468, 326)"
                                    readOnly
                                    className="w-full px-3 py-2 bg-surface border border-white/10 rounded-lg text-text-primary text-sm font-mono"
                                />
                            </div>

                            <div>
                                <label className="text-sm text-text-secondary mb-2 block">Type text</label>
                                <input
                                    type="text"
                                    placeholder="Click on an input to start..."
                                    className="w-full px-3 py-2 bg-surface border border-white/10 rounded-lg text-text-primary text-sm"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Automation Status */}
                    <div className="glass rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-text-primary mb-4">Automation Status</h3>

                        <div className="space-y-3">
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm text-text-secondary">Current Step</span>
                                    <span className="text-xs px-2 py-1 rounded-full bg-primary/20 text-primary">In Progress</span>
                                </div>
                                <div className="px-3 py-2 bg-surface/50 rounded-lg border border-primary/30">
                                    <p className="text-sm text-text-primary">{currentStep}</p>
                                </div>
                            </div>

                            <div>
                                <span className="text-sm text-text-secondary block mb-2">Next Step</span>
                                <div className="px-3 py-2 bg-surface/50 rounded-lg border border-white/10">
                                    <p className="text-sm text-text-secondary">{nextStep}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Frame Info */}
                    <div className="glass rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-text-primary mb-4">Frame Info</h3>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-secondary">FPS</span>
                                <span className="text-sm text-success font-mono">15</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-secondary">Resolution</span>
                                <span className="text-sm text-text-primary font-mono">1280x720</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-secondary">Quality</span>
                                <span className="text-sm text-text-primary">High</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
