"use client";

import ProgressTimeline from "@/components/ProgressTimeline";
import ProductCard from "@/components/ProductCard";
import ProductDetailsPreview from "@/components/ProductDetailsPreview";
import { Play } from "lucide-react";
import { useState } from "react";

export default function Home() {
  const [isAutomationRunning, setIsAutomationRunning] = useState(false);

  const startAutomation = async () => {
    // try {
    //   setIsAutomationRunning(true);
    //
    //   // Fetch from LLM agent instead of legacy agent
    //   const response = await fetch("http://localhost:8000/api/chat/llm/data");
    //   const data = await response.json();
    //
    //   // Send LLM-generated checkout data to automation
    //   await fetch("http://localhost:8000/api/automation/start", {
    //     method: "POST",
    //     headers: { "Content-Type": "application/json" },
    //     body: JSON.stringify(data.checkout_data),
    //   });
    // } catch (error) {
    //   console.error("Error starting automation:", error);
    //   setIsAutomationRunning(false);
    // }
    alert("Automation trigger is currently disabled as the chat system has been removed.");
  };

  return (
    <div className="flex h-screen">
      {/* Main Area (formerly Chat) */}
      <div className="flex-1 flex flex-col items-center justify-center text-text-secondary">
        <h2 className="text-2xl font-bold mb-2">Checkout Automation</h2>
        <p>Chat system has been removed.</p>
        <p className="text-sm mt-4">Please use the controls on the right to manage state.</p>
      </div>

      {/* Right Sidebar */}
      <div className="w-96 border-l border-white/10 p-6 space-y-6 overflow-y-auto">
        {/* Product Details Preview */}
        <ProductDetailsPreview />

        {/* Progress Timeline */}
        <ProgressTimeline />

        {/* Product Card */}
        <ProductCard />

        {/* Quick Actions */}
        <div className="glass rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-semibold text-text-primary">Quick Actions</h3>

          <div>
            <label className="text-sm text-text-secondary mb-2 block">Saved Addresses</label>
            <select className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary">
              <option>Select address...</option>
            </select>
          </div>

          <div>
            <label className="text-sm text-text-secondary mb-2 block">Payment Methods</label>
            <select className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary">
              <option>Select payment...</option>
            </select>
          </div>

          <button
            onClick={startAutomation}
            disabled={isAutomationRunning}
            className="w-full py-3 bg-success text-black font-bold rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity flex items-center justify-center gap-2"
          >
            <Play size={20} />
            {isAutomationRunning ? "Running..." : "Start Checkout"}
          </button>
        </div>
      </div>
    </div>
  );
}
