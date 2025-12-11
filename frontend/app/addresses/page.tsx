"use client";

import { useState, useEffect } from "react";
import { MapPin, Plus, Trash2, Star } from "lucide-react";

interface Address {
    id: string;
    type: string;
    full_name: string;
    address_line1: string;
    address_line2?: string;
    city: string;
    state: string;
    postal_code: string;
    country: string;
    phone?: string;
    is_default: boolean;
}

export default function AddressesPage() {
    const [addresses, setAddresses] = useState<Address[]>([]);
    const [showAddAddress, setShowAddAddress] = useState(false);

    useEffect(() => {
        fetchAddresses();
    }, []);

    const fetchAddresses = async () => {
        try {
            const response = await fetch("http://localhost:8000/api/addresses");
            const data = await response.json();
            setAddresses(data);
        } catch (error) {
            console.error("Error fetching addresses:", error);
        }
    };

    const deleteAddress = async (id: string) => {
        if (!confirm("Are you sure you want to delete this address?")) return;

        try {
            await fetch(`http://localhost:8000/api/addresses/${id}`, {
                method: "DELETE",
            });
            fetchAddresses();
        } catch (error) {
            console.error("Error deleting address:", error);
        }
    };

    return (
        <div className="p-8">
            <div className="max-w-4xl mx-auto">
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

                {/* Addresses List */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {addresses.length === 0 ? (
                        <div className="col-span-2 glass rounded-xl p-12 text-center">
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
                                        <h3 className="text-text-primary font-semibold">{address.type}</h3>
                                        {address.is_default && (
                                            <span className="px-2 py-1 bg-success/20 text-success text-xs rounded-full flex items-center gap-1">
                                                <Star size={12} />
                                                Default
                                            </span>
                                        )}
                                    </div>
                                    <button
                                        onClick={() => deleteAddress(address.id)}
                                        className="p-2 hover:bg-error/20 rounded-lg transition-colors"
                                    >
                                        <Trash2 size={16} className="text-error" />
                                    </button>
                                </div>
                                <div className="text-sm text-text-secondary space-y-1">
                                    <p className="text-text-primary font-medium">{address.full_name}</p>
                                    <p>{address.address_line1}</p>
                                    {address.address_line2 && <p>{address.address_line2}</p>}
                                    <p>{address.city}, {address.state} {address.postal_code}</p>
                                    <p>{address.country}</p>
                                    {address.phone && <p>Phone: {address.phone}</p>}
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Add Address Modal */}
                {showAddAddress && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                        <div className="glass rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
                            <h2 className="text-xl font-bold text-text-primary mb-4">Add Address</h2>
                            <form className="space-y-4">
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Full Name</label>
                                    <input
                                        type="text"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Address Line 1</label>
                                    <input
                                        type="text"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Address Line 2 (Optional)</label>
                                    <input
                                        type="text"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">City</label>
                                        <input
                                            type="text"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">State</label>
                                        <input
                                            type="text"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Postal Code</label>
                                        <input
                                            type="text"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm text-text-secondary mb-2 block">Country</label>
                                        <input
                                            type="text"
                                            className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label className="text-sm text-text-secondary mb-2 block">Phone (Optional)</label>
                                    <input
                                        type="text"
                                        className="w-full px-4 py-2 bg-surface border border-white/10 rounded-lg text-text-primary focus:outline-none focus:border-primary"
                                    />
                                </div>
                                <div className="flex gap-3 mt-6">
                                    <button
                                        type="button"
                                        onClick={() => setShowAddAddress(false)}
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
