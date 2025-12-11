"use client";

import { useEffect, useState } from "react";

interface JSONData {
    tasks?: Array<{
        url?: string;
        productName?: string;
        variants?: Record<string, string>;
        quantity?: number;
    }>;
    customer?: {
        shippingAddress?: Record<string, string>;
        billingAddress?: Record<string, string>;
        paymentMethod?: Record<string, any>;
    };
}

export default function JSONPreview() {
    const [jsonData, setJsonData] = useState<JSONData>({});
    const [isExpanded, setIsExpanded] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/data/current");
                const data = await response.json();
                setJsonData(data.json_data || {});
            } catch (error) {
                console.error("Error fetching JSON data:", error);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 2000);
        return () => clearInterval(interval);
    }, []);

    const formatJSON = (obj: any, indent = 0): React.ReactNode[] => {
        const elements: React.ReactNode[] = [];
        const spacing = "  ".repeat(indent);

        Object.entries(obj).forEach(([key, value], index) => {
            if (typeof value === "object" && value !== null && !Array.isArray(value)) {
                elements.push(
                    <div key={`${key}-${index}`} className="leading-relaxed">
                        <span className="text-text-secondary">{spacing}</span>
                        <span className="json-key">&quot;{key}&quot;</span>
                        <span className="text-text-secondary">: &#123;</span>
                        {formatJSON(value, indent + 1)}
                        <span className="text-text-secondary">{spacing}&#125;</span>
                    </div>
                );
            } else if (Array.isArray(value)) {
                elements.push(
                    <div key={`${key}-${index}`} className="leading-relaxed">
                        <span className="text-text-secondary">{spacing}</span>
                        <span className="json-key">&quot;{key}&quot;</span>
                        <span className="text-text-secondary">: [</span>
                        {value.map((item, i) => (
                            <div key={i}>
                                {typeof item === "object" ? formatJSON(item, indent + 1) : (
                                    <span className="text-text-secondary">{spacing}  {JSON.stringify(item)}</span>
                                )}
                            </div>
                        ))}
                        <span className="text-text-secondary">{spacing}]</span>
                    </div>
                );
            } else {
                const valueClass =
                    typeof value === "string" ? "json-string" :
                        typeof value === "number" ? "json-number" :
                            typeof value === "boolean" ? "json-boolean" :
                                "text-text-secondary";

                elements.push(
                    <div key={`${key}-${index}`} className="leading-relaxed">
                        <span className="text-text-secondary">{spacing}</span>
                        <span className="json-key">&quot;{key}&quot;</span>
                        <span className="text-text-secondary">: </span>
                        <span className={valueClass}>
                            {typeof value === "string" ? `"${value}"` : String(value)}
                        </span>
                    </div>
                );
            }
        });

        return elements;
    };

    return (
        <div className="border-t border-primary/50 glass mt-4 rounded-b-xl">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-6 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
            >
                <span className="text-sm font-semibold text-text-primary">JSON Preview</span>
                <svg
                    className={`w-5 h-5 text-text-secondary transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {isExpanded && (
                <div className="px-6 pb-6 max-h-96 overflow-y-auto">
                    <div className="glass rounded-lg p-4 font-mono text-xs">
                        <div className="text-text-secondary">&#123;</div>
                        {formatJSON(jsonData, 1)}
                        <div className="text-text-secondary">&#125;</div>
                    </div>
                </div>
            )}
        </div>
    );
}
