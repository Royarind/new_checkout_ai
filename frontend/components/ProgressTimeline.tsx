"use client";

import { CheckCircle, Circle, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

interface Step {
    name: string;
    status: "completed" | "in-progress" | "pending";
}

export default function ProgressTimeline() {
    const [steps, setSteps] = useState<Step[]>([
        { name: "Navigate to Product", status: "pending" },
        { name: "Select Variants", status: "pending" },
        { name: "Add to Cart", status: "pending" },
        { name: "Checkout", status: "pending" },
        { name: "Payment", status: "pending" },
    ]);
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        // Connect to WebSocket for real-time updates
        const ws = new WebSocket("ws://localhost:8000/ws/progress");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === "progress") {
                const stepIndex = steps.findIndex(s => s.name.toLowerCase().includes(data.phase.toLowerCase()));
                if (stepIndex !== -1) {
                    setSteps(prev => prev.map((step, idx) => ({
                        ...step,
                        status: idx < stepIndex ? "completed" : idx === stepIndex ? "in-progress" : "pending"
                    })));
                    setProgress(((stepIndex + 1) / steps.length) * 100);
                }
            }
        };

        return () => ws.close();
    }, []);

    return (
        <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-text-primary">Automation Progress</h3>
                <span className="text-sm font-bold gradient-text">{Math.round(progress)}%</span>
            </div>

            {/* Animated Progress Bar */}
            <div className="w-full h-2 bg-surface rounded-full mb-8 overflow-hidden relative">
                <div
                    className="h-full gradient-primary transition-all duration-700 ease-out glow-primary"
                    style={{ width: `${progress}%` }}
                />
            </div>

            {/* Connected Steps with Vertical Line */}
            <div className="relative space-y-6">
                {steps.map((step, index) => (
                    <div key={index} className="relative flex items-start gap-4">
                        {/* Vertical connecting line */}
                        {index < steps.length - 1 && (
                            <div className="absolute left-[10px] top-[28px] w-0.5 h-[calc(100%+8px)] bg-surface">
                                {step.status === "completed" && (
                                    <div className="w-full gradient-primary progress-line"></div>
                                )}
                            </div>
                        )}

                        {/* Status Icon */}
                        <div className="relative z-10 flex-shrink-0">
                            {step.status === "completed" && (
                                <div className="w-5 h-5 rounded-full bg-success flex items-center justify-center glow-success">
                                    <CheckCircle size={20} className="text-white" />
                                </div>
                            )}
                            {step.status === "in-progress" && (
                                <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center pulse-glow">
                                    <Loader2 size={16} className="text-white animate-spin" />
                                </div>
                            )}
                            {step.status === "pending" && (
                                <Circle size={20} className="text-text-secondary" />
                            )}
                        </div>

                        {/* Step Label */}
                        <div className="flex-1 pt-0.5">
                            <span
                                className={`text-sm font-medium ${step.status === "pending"
                                        ? "text-text-secondary"
                                        : step.status === "completed"
                                            ? "text-success"
                                            : "text-primary"
                                    }`}
                            >
                                {step.name}
                            </span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
