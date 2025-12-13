"use client";

import { useState, useEffect } from "react";
import { MapPin, Plus, Trash2, Star } from "lucide-react";
import {
    getAddresses,
    saveAddress,
    deleteAddress,
    setDefaultAddress,
    type Address,
} from "@/utils/localStorage";

export default function AddressesPage() {
    const [addresses, setAddresses] = useState<Address[]>([]);
    const [showAddAddress, setShowAddAddress] = useState(false);
    const [formData, setFormData] = useState({
        type: "shipping" as "shipping" | "billing",
        fullName: "",
        addressLine1: "",
        addressLine2: "",
        city: "",
        state: "",
        postalCode: "",
        country: "",
        phone: "",
    });

    useEffect(() => {
        loadAddresses();
    }, []);

    const loadAddresses = () => {
        setAddresses(getAddresses());
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        saveAddress({
            ...formData,
            isDefault: addresses.length === 0,
        });

        loadAddresses();
        setShowAddAddress(false);
        resetForm();
    };

    const resetForm = () => {
        setFormData({
            type: "shipping",
            fullName: "",
            addressLine1: "",
            addressLine2: "",
            city: "",
            state: "",
            postalCode: "",
            country: "",
            phone: "",
        });
    };

    const handleDelete = (id: string) => {
        if (confirm("Are you sure you want to delete this address?")) {
            deleteAddress(id);
            loadAddresses();
        }
    };

    const handleSetDefault = (id: string) => {
        setDefaultAddress(id);
        loadAddresses();
    };

    return (
        <div className="p-8">
            <div className="max-w-6xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-text-primary">Addresses</h1>
                        <p className="text-text-secondary mt-1">Manage your saved addresses</p>
                    </div>
                    <button
                        onClick={() => setShowAddAddress(true)}
                        className="px-4 py-2 gradient-primary text-white rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
                    >
                        <Plus size={20} />
                        Add Address
                    </button>
                </div>

                {/* Addresses Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {addresses.length === 0 ? (
                        <div className="col-span-full glass rounded-xl p-12 text-center">
                            <MapPin size={48} className="mx-auto text-text-secondary mb-4" />
                            <p className="text-text-secondary">No addresses saved yet</p>
                            <button
                                onClick={() => setShowAddAddress(true)}
                                className="mt-4 px-6 py-2 gradient-primary text-white rounded-lg hover:opacity-90"
                            >
                                Add Your First Address
                            </button>
                        </div>
                    ) : (
                        addresses.map((address) => (
                            <div key={address.id} className="glass rounded-xl p-6">
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <MapPin size={20} className="text-primary" />
                                        <h3 className="text-text-primary font-semibold capitalize">{address.type}</h3>
                                        {address.isDefault && (
                                            <span className="px-2 py-1 bg-success/20 text-success text-xs rounded-full flex items-center gap-1">
                                                <Star size={12} fill="currentColor" />
                                                Default
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1">
                                        {!address.isDefault && (
                                            <button
                                                onClick={() => handleSetDefault(address.id)}
                                                className="p-2 hover:bg-success/20 rounded-lg transition-colors group"
                                                title="Set as default"
                                            >
                                                <Star size={16} className="text-text-secondary group-hover:text-success" />
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleDelete(address.id)}
                                            className="p-2 hover:bg-error/20 rounded-lg transition-colors"
                                            title="Delete"
                                        >
                                            <Trash2 size={16} className="text-error" />
                                        </button>
                                    </div>
                                </div>
                                <div className="text-sm text-text-secondary space-y-1">
                                    <p className="text-text-primary font-medium">{address.fullName}</p>
                                    <p>{address.addressLine1}</p>
                                    {address.addressLine2 && <p>{address.addressLine2}</p>}
                                    <p>{address.city}, {address.state} {address.postalCode}</p>
                                    <p>{address.country}</p>
                                    {address.phone && <p>Phone: {address.phone}</p>}
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Add Address Modal */}
                {showAddAddress && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowAddAddress(false)}>
                        <div className="glass rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                            <h2 className="text-xl font-bold text-text-primary mb-4">Add Address</h2>
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Address Type</label>
                                    <select
                                        value={formData.type}
                                        onChange={(e) => setFormData({ ...formData, type: e.target.value as "shipping" | "billing" })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    >
                                        <option value="shipping">Shipping</option>
                                        <option value="billing">Billing</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Full Name</label>
                                    <input
                                        type="text"
                                        value={formData.fullName}
                                        onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Address Line 1</label>
                                    <input
                                        type="text"
                                        value={formData.addressLine1}
                                        onChange={(e) => setFormData({ ...formData, addressLine1: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Address Line 2 (Optional)</label>
                                    <input
                                        type="text"
                                        value={formData.addressLine2}
                                        onChange={(e) => setFormData({ ...formData, addressLine2: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">City</label>
                                        <input
                                            type="text"
                                            value={formData.city}
                                            onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">State</label>
                                        <input
                                            type="text"
                                            value={formData.state}
                                            onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Postal Code</label>
                                        <input
                                            type="text"
                                            value={formData.postalCode}
                                            onChange={(e) => setFormData({ ...formData, postalCode: e.target.value })}
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Country</label>
                                        <input
                                            type="text"
                                            value={formData.country}
                                            onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                            required
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Phone (Optional)</label>
                                    <input
                                        type="text"
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div className="flex gap-3 mt-6">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowAddAddress(false);
                                            resetForm();
                                        }}
                                        className="flex-1 px-4 py-2 bg-surface border border-white/10 text-text-primary rounded-lg hover:bg-white/5"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="flex-1 px-4 py-2 gradient-primary text-white rounded-lg hover:opacity-90"
                                    >
                                        Save Address
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
