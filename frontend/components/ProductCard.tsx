"use client";

import { useEffect, useState } from "react";
import { Package, Minus, Plus } from "lucide-react";

interface ProductData {
    url?: string;
    name?: string;
    variants?: Record<string, string>;
    quantity?: number;
}

export default function ProductCard() {
    const [product, setProduct] = useState<ProductData>({});

    useEffect(() => {
        // Fetch product data
        const fetchData = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/data/structured");
                const data = await response.json();
                setProduct(data.product || {});
            } catch (error) {
                console.error("Error fetching product data:", error);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 2000); // Poll every 2 seconds
        return () => clearInterval(interval);
    }, []);

    if (!product.name) {
        return (
            <div className="glass rounded-xl p-6">
                <div className="flex items-center gap-3 text-text-secondary">
                    <Package size={20} />
                    <span className="text-sm">No product selected</span>
                </div>
            </div>
        );
    }

    return (
        <div className="glass rounded-xl p-6">
            <h3 className="text-lg font-semibold text-text-primary mb-4">Product Details</h3>

            {/* Product Info */}
            <div className="space-y-3">
                <div>
                    <p className="text-sm text-text-secondary mb-1">Product</p>
                    <p className="text-text-primary font-medium">{product.name}</p>
                </div>

                {/* Variants */}
                {product.variants && Object.keys(product.variants).length > 0 && (
                    <div>
                        <p className="text-sm text-text-secondary mb-2">Variants</p>
                        <div className="flex flex-wrap gap-2">
                            {Object.entries(product.variants).map(([key, value]) => (
                                <span
                                    key={key}
                                    className="px-3 py-1 bg-primary/20 text-primary rounded-full text-xs font-medium"
                                >
                                    {key}: {value}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Quantity */}
                <div>
                    <p className="text-sm text-text-secondary mb-2">Quantity</p>
                    <div className="flex items-center gap-2">
                        <button className="w-8 h-8 rounded-lg bg-surface border border-white/10 flex items-center justify-center hover:bg-white/5">
                            <Minus size={16} className="text-text-primary" />
                        </button>
                        <span className="w-12 text-center text-text-primary font-medium">
                            {product.quantity || 1}
                        </span>
                        <button className="w-8 h-8 rounded-lg bg-surface border border-white/10 flex items-center justify-center hover:bg-white/5">
                            <Plus size={16} className="text-text-primary" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
