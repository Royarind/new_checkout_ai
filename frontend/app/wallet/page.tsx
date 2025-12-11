"use client";

import { useState, useEffect } from "react";
import { CreditCard, Plus, Trash2, Star } from "lucide-react";

interface PaymentMethod {
    id: string;
    type: string;
    label: string;
    masked_data: string;
    is_default: boolean;
}

export default function WalletPage() {
    const [methods, setMethods] = useState<PaymentMethod[]>([]);
    const [showAddCard, setShowAddCard] = useState(false);

    useEffect(() => {
        fetchMethods();
    }, []);

    const fetchMethods = async () => {
        try {
            const response = await fetch("http://localhost:8000/api/wallet/methods");
            const data = await response.json();
            setMethods(data);
        } catch (error) {
            console.error("Error fetching payment methods:", error);
        }
    };

    const deleteMethod = async (id: string) => {
        if (!confirm("Are you sure you want to delete this payment method?")) return;

        try {
            await fetch(`http://localhost:8000/api/wallet/methods/${id}`, {
                method: "DELETE",
            });
            fetchMethods();
        } catch (error) {
            console.error("Error deleting payment method:", error);
        }
    };

    return (
        <div className="p-8">
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-text-primary">Wallet</h1>
                        <p className="text-text-secondary mt-1">Manage your payment methods</p>
                    </div>
                    <button
                        onClick={() => setShowAddCard(true)}
                        className="px-4 py-2 gradient-primary text-white rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
                    >
                        <Plus size={20} />
                        Add Payment Method
                    </button>
                </div>

                {/* Payment Methods List */}
                <div className="space-y-4">
                    {methods.length === 0 ? (
                        <div className="glass rounded-xl p-12 text-center">
                            <CreditCard size={48} className="mx-auto text-text-secondary mb-4" />
                            <p className="text-text-secondary">No payment methods saved yet</p>
                            <button
                                onClick={() => setShowAddCard(true)}
                                className="mt-4 px-6 py-2 gradient-primary text-white rounded-lg hover:opacity-90"
                            >
                                Add Your First Payment Method
                            </button>
                        </div>
                    ) : (
                        methods.map((method) => (
                            <div key={method.id} className="glass rounded-xl p-6 flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center">
                                        <CreditCard size={24} className="text-primary" />
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <h3 className="text-text-primary font-semibold">{method.label}</h3>
                                            {method.is_default && (
                                                <span className="px-2 py-1 bg-success/20 text-success text-xs rounded-full flex items-center gap-1">
                                                    <Star size={12} />
                                                    Default
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-text-secondary text-sm mt-1">{method.masked_data}</p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => deleteMethod(method.id)}
                                    className="p-2 hover:bg-error/20 rounded-lg transition-colors"
                                >
                                    <Trash2 size={20} className="text-error" />
                                </button>
                            </div>
                        ))
                    )}
                </div>

                {/* Add Card Modal */}
                {showAddCard && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                        <div className="glass rounded-xl p-6 w-full max-w-md">
                            <h2 className="text-xl font-bold text-text-primary mb-4">Add Payment Method</h2>
                            <form className="space-y-4">
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Card Number</label>
                                    <input
                                        type="text"
                                        placeholder="1234 5678 9012 3456"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Cardholder Name</label>
                                    <input
                                        type="text"
                                        placeholder="John Doe"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Expiry</label>
                                        <input
                                            type="text"
                                            placeholder="MM/YY"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">CVV</label>
                                        <input
                                            type="text"
                                            placeholder="123"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                </div>
                                <div className="flex gap-3 mt-6">
                                    <button
                                        type="button"
                                        onClick={() => setShowAddCard(false)}
                                        className="flex-1 px-4 py-2 bg-surface border border-white/10 text-text-primary rounded-lg hover:bg-white/5"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="flex-1 px-4 py-2 gradient-primary text-white rounded-lg hover:opacity-90"
                                    >
                                        Save
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
