"use client";

import { useState, useEffect } from "react";
import { CreditCard, Plus, Trash2, Star, Edit2, Check } from "lucide-react";
import CardLogo from "@/components/CardLogo";
import {
    getPaymentMethods,
    savePaymentMethod,
    deletePaymentMethod,
    setDefaultPaymentMethod,
    type PaymentMethod,
    type CardData,
} from "@/utils/localStorage";

export default function WalletPage() {
    const [methods, setMethods] = useState<PaymentMethod[]>([]);
    const [showAddCard, setShowAddCard] = useState(false);
    const [cardData, setCardData] = useState<CardData>({
        cardNumber: "",
        cardHolder: "",
        expiryMonth: "",
        expiryYear: "",
        cvv: "",
    });

    useEffect(() => {
        loadMethods();
    }, []);

    const loadMethods = () => {
        setMethods(getPaymentMethods());
    };

    const handleAddCard = (e: React.FormEvent) => {
        e.preventDefault();

        // Parse expiry (MM/YY format)
        const expiry = (e.target as any).expiry.value.split("/");

        const newCardData: CardData = {
            cardNumber: cardData.cardNumber,
            cardHolder: cardData.cardHolder,
            expiryMonth: expiry[0]?.trim() || "",
            expiryYear: expiry[1]?.trim() || "",
            cvv: cardData.cvv,
        };

        savePaymentMethod("card", newCardData, undefined, methods.length === 0);
        loadMethods();
        setShowAddCard(false);
        setCardData({
            cardNumber: "",
            cardHolder: "",
            expiryMonth: "",
            expiryYear: "",
            cvv: "",
        });
    };

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this payment method?")) {
            deletePaymentMethod(id);
            loadMethods();
        }
    };

    const handleSetDefault = (id: string) => {
        setDefaultPaymentMethod(id);
        loadMethods();
    };

    const getCardGradient = (cardType: string) => {
        const gradients = {
            visa: "from-indigo-600 via-purple-500 to-pink-500",
            mastercard: "from-rose-600 via-orange-500 to-amber-400",
            amex: "from-cyan-500 via-teal-400 to-emerald-400",
            discover: "from-orange-500 via-pink-500 to-purple-600",
            unknown: "from-slate-700 via-blue-600 to-purple-600",
        };
        return gradients[cardType as keyof typeof gradients] || gradients.unknown;
    };

    return (
        <div className="p-8">
            <div className="max-w-6xl mx-auto">
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
                        Add Card
                    </button>
                </div>

                {/* Payment Methods Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {methods.length === 0 ? (
                        <div className="col-span-full glass rounded-xl p-12 text-center">
                            <CreditCard size={48} className="mx-auto text-text-secondary mb-4" />
                            <p className="text-text-secondary">No payment methods saved yet</p>
                            <button
                                onClick={() => setShowAddCard(true)}
                                className="mt-4 px-6 py-2 gradient-primary text-white rounded-lg hover:opacity-90"
                            >
                                Add Your First Card
                            </button>
                        </div>
                    ) : (
                        methods.map((method) => (
                            <div key={method.id} className="group relative">
                                {/* Realistic Credit Card */}
                                <div className={`relative w-full aspect-[1.586/1] rounded-2xl bg-gradient-to-br ${getCardGradient(method.cardType || "unknown")} p-6 shadow-2xl transform transition-all duration-300 hover:scale-105 hover:shadow-3xl`}>
                                    {/* Card Background Pattern */}
                                    <div className="absolute inset-0 opacity-10">
                                        <div className="absolute top-0 right-0 w-32 h-32 bg-white rounded-full blur-3xl"></div>
                                        <div className="absolute bottom-0 left-0 w-40 h-40 bg-white rounded-full blur-3xl"></div>
                                    </div>

                                    {/* Card Content */}
                                    <div className="relative h-full flex flex-col justify-between text-white">
                                        {/* Top Row: Chip and Logo */}
                                        <div className="flex items-start justify-between">
                                            <div className="w-12 h-10 rounded-md bg-gradient-to-br from-yellow-200 to-yellow-400 shadow-lg flex items-center justify-center">
                                                <div className="w-8 h-6 rounded-sm bg-gradient-to-br from-yellow-300 to-yellow-500 opacity-80"></div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {method.isDefault && (
                                                    <div className="px-2 py-1 bg-white/20 backdrop-blur-sm rounded-full flex items-center gap-1 text-xs">
                                                        <Star size={12} fill="currentColor" />
                                                        Default
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Middle: Card Number */}
                                        <div className="space-y-4">
                                            <div className="font-mono text-xl tracking-wider">
                                                {method.maskedData}
                                            </div>

                                            {/* Bottom Row: Name and Expiry */}
                                            <div className="flex items-end justify-between">
                                                <div>
                                                    <div className="text-xs opacity-70 uppercase tracking-wide">Cardholder</div>
                                                    <div className="font-semibold text-sm uppercase tracking-wide mt-1">
                                                        {method.label}
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-xs opacity-70 uppercase tracking-wide">Expires</div>
                                                    <div className="font-mono text-sm mt-1">
                                                        {/* Extract expiry from encrypted data if available */}
                                                        **/**
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Card Brand Logo */}
                                        <div className="absolute bottom-6 right-6">
                                            <div className="text-right">
                                                <div className="text-2xl font-bold uppercase tracking-wider opacity-90">
                                                    {method.cardType === 'visa' && 'VISA'}
                                                    {method.cardType === 'mastercard' && 'Mastercard'}
                                                    {method.cardType === 'amex' && 'AMEX'}
                                                    {method.cardType === 'discover' && 'DISCOVER'}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Holographic Effect */}
                                    <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/0 via-white/10 to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                                </div>

                                {/* Action Buttons */}
                                <div className="mt-4 flex items-center justify-center gap-2">
                                    {!method.isDefault && (
                                        <button
                                            onClick={() => handleSetDefault(method.id)}
                                            className="p-2 glass rounded-lg hover:bg-success/20 transition-colors group/btn"
                                            title="Set as default"
                                        >
                                            <Star size={18} className="text-text-secondary group-hover/btn:text-success" />
                                        </button>
                                    )}
                                    <button
                                        onClick={() => handleDelete(method.id)}
                                        className="p-2 glass rounded-lg hover:bg-error/20 transition-colors group/btn"
                                        title="Delete"
                                    >
                                        <Trash2 size={18} className="text-text-secondary group-hover/btn:text-error" />
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Add Card Modal */}
                {showAddCard && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddCard(false)}>
                        <div className="glass rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                            <h2 className="text-xl font-bold text-text-primary mb-4">Add Payment Card</h2>
                            <form onSubmit={handleAddCard} className="space-y-4">
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Card Number</label>
                                    <input
                                        type="text"
                                        placeholder="1234 5678 9012 3456"
                                        value={cardData.cardNumber}
                                        onChange={(e) => setCardData({ ...cardData, cardNumber: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        required
                                        maxLength={19}
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Cardholder Name</label>
                                    <input
                                        type="text"
                                        placeholder="John Doe"
                                        value={cardData.cardHolder}
                                        onChange={(e) => setCardData({ ...cardData, cardHolder: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        required
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Expiry</label>
                                        <input
                                            type="text"
                                            name="expiry"
                                            placeholder="MM/YY"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                            maxLength={5}
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">CVV</label>
                                        <input
                                            type="text"
                                            placeholder="123"
                                            value={cardData.cvv}
                                            onChange={(e) => setCardData({ ...cardData, cvv: e.target.value })}
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                            maxLength={4}
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
                                        Save Card
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
