"use client";

import { useEffect, useState } from "react";
import { Package, ExternalLink } from "lucide-react";

interface ProductDetails {
    url?: string;
    variants?: {
        color?: string;
        size?: string;
        [key: string]: any;
    };
    quantity?: number;
}

export default function ProductDetailsPreview() {
    const [productData, setProductData] = useState<ProductDetails>({});
    const [thumbnail, setThumbnail] = useState<string>("");

    useEffect(() => {
        const fetchProductData = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/chat/llm/data");
                const data = await response.json();

                if (data.checkout_data?.tasks?.[0]) {
                    const task = data.checkout_data.tasks[0];
                    setProductData({
                        url: task.url,
                        variants: task.selectedVariant || {},  // Changed from variants to selectedVariant
                        quantity: task.quantity || 1
                    });

                    // Extract thumbnail from URL
                    if (task.url) {
                        extractThumbnail(task.url);
                    }
                }
            } catch (error) {
                console.error("Error fetching product data:", error);
            }
        };

        fetchProductData();
        const interval = setInterval(fetchProductData, 2000);
        return () => clearInterval(interval);
    }, []);

    const extractThumbnail = async (url: string) => {
        try {
            const response = await fetch(`http://localhost:8000/api/product/info?url=${encodeURIComponent(url)}`);
            const data = await response.json();

            if (data.thumbnail) {
                setThumbnail(data.thumbnail);
            } else {
                // Fallback to placeholder if scraping fails
                setThumbnail(`https://via.placeholder.com/200x200/1a1a2e/6c63ff?text=Product`);
            }
        } catch (error) {
            console.error("Error fetching thumbnail:", error);
            setThumbnail(`https://via.placeholder.com/200x200/1a1a2e/6c63ff?text=Product`);
        }
    };

    if (!productData.url) {
        return (
            <div className="glass rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Package size={20} className="text-primary" />
                    <h3 className="text-lg font-semibold text-text-primary">Product Details</h3>
                </div>
                <p className="text-text-secondary text-sm">No product selected yet</p>
            </div>
        );
    }

    return (
        <div className="glass rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
                <Package size={20} className="text-primary" />
                <h3 className="text-lg font-semibold text-text-primary">Product Details</h3>
            </div>

            <div className="space-y-4">
                {/* Product Thumbnail */}
                {thumbnail && (
                    <div className="w-full aspect-square rounded-lg overflow-hidden bg-surface border border-white/10">
                        <img
                            src={thumbnail}
                            alt="Product"
                            className="w-full h-full object-cover"
                        />
                    </div>
                )}

                {/* Product URL */}
                <div>
                    <label className="text-xs text-text-secondary uppercase tracking-wide">Product URL</label>
                    <a
                        href={productData.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 mt-1 text-sm text-primary hover:underline break-all"
                    >
                        <ExternalLink size={14} />
                        {productData.url}
                    </a>
                </div>

                {/* Variants */}
                {productData.variants && Object.keys(productData.variants).length > 0 && (
                    <div className="grid grid-cols-2 gap-3">
                        {productData.variants.color && (
                            <div>
                                <label className="text-xs text-text-secondary uppercase tracking-wide">Color</label>
                                <p className="text-sm text-text-primary mt-1 font-medium">{productData.variants.color}</p>
                            </div>
                        )}
                        {productData.variants.size && (
                            <div>
                                <label className="text-xs text-text-secondary uppercase tracking-wide">Size</label>
                                <p className="text-sm text-text-primary mt-1 font-medium">{productData.variants.size}</p>
                            </div>
                        )}
                        {Object.entries(productData.variants).map(([key, value]) => {
                            if (key !== 'color' && key !== 'size' && value) {
                                return (
                                    <div key={key}>
                                        <label className="text-xs text-text-secondary uppercase tracking-wide">{key}</label>
                                        <p className="text-sm text-text-primary mt-1 font-medium">{String(value)}</p>
                                    </div>
                                );
                            }
                            return null;
                        })}
                    </div>
                )}

                {/* Quantity */}
                {productData.quantity && (
                    <div>
                        <label className="text-xs text-text-secondary uppercase tracking-wide">Quantity</label>
                        <p className="text-sm text-text-primary mt-1 font-medium">{productData.quantity}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
