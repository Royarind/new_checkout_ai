import { useState, useEffect } from 'react';
import { User, MapPin, CreditCard, Shield, Plus, Trash2, Star } from 'lucide-react';
import { apiCall } from '../hooks/useAuth';
import './Settings.css';

interface ProfileData {
    id: number;
    email: string;
    full_name: string;
    phone: string;
    country: string;
}

interface Address {
    id: number;
    label: string;
    recipient_name?: string;
    full_name?: string;
    address_line1: string;
    address_line2: string;
    city: string;
    state: string;
    postal_code: string;
    country: string;
    is_default: number;
}

export const Settings = () => {
    const [activeTab, setActiveTab] = useState('personal');
    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [shippingAddresses, setShippingAddresses] = useState<Address[]>([]);
    const [billingAddresses, setBillingAddresses] = useState<Address[]>([]);
    const [showAddShipping, setShowAddShipping] = useState(false);
    const [showAddBilling, setShowAddBilling] = useState(false);

    useEffect(() => {
        fetchProfile();
        fetchShippingAddresses();
        fetchBillingAddresses();
    }, []);

    const fetchProfile = async () => {
        try {
            const response = await apiCall('/api/profile');
            const data = await response.json();
            setProfile(data);
        } catch (error) {
            console.error('Failed to fetch profile:', error);
        }
    };

    const fetchShippingAddresses = async () => {
        try {
            const response = await apiCall('/api/profile/shipping-addresses');
            const data = await response.json();
            setShippingAddresses(data);
        } catch (error) {
            console.error('Failed to fetch shipping addresses:', error);
        }
    };

    const fetchBillingAddresses = async () => {
        try {
            const response = await apiCall('/api/profile/billing-addresses');
            const data = await response.json();
            setBillingAddresses(data);
        } catch (error) {
            console.error('Failed to fetch billing addresses:', error);
        }
    };

    const handleUpdateProfile = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        try {
            await apiCall('/api/profile', {
                method: 'PUT',
                body: JSON.stringify({
                    full_name: formData.get('full_name'),
                    phone: formData.get('phone'),
                    country: formData.get('country')
                })
            });
            alert('Profile updated successfully!');
            fetchProfile();
        } catch (error) {
            alert('Failed to update profile');
        }
    };

    const handleAddShippingAddress = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        try {
            await apiCall('/api/profile/shipping-addresses', {
                method: 'POST',
                body: JSON.stringify({
                    label: formData.get('label'),
                    recipient_name: formData.get('recipient_name'),
                    address_line1: formData.get('address_line1'),
                    address_line2: formData.get('address_line2'),
                    city: formData.get('city'),
                    state: formData.get('state'),
                    postal_code: formData.get('postal_code'),
                    country: formData.get('country'),
                    is_default: formData.get('is_default') === 'on'
                })
            });
            setShowAddShipping(false);
            fetchShippingAddresses();
        } catch (error) {
            alert('Failed to add shipping address');
        }
    };

    const handleAddBillingAddress = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        try {
            await apiCall('/api/profile/billing-addresses', {
                method: 'POST',
                body: JSON.stringify({
                    label: formData.get('label'),
                    full_name: formData.get('full_name'),
                    address_line1: formData.get('address_line1'),
                    address_line2: formData.get('address_line2'),
                    city: formData.get('city'),
                    state: formData.get('state'),
                    postal_code: formData.get('postal_code'),
                    country: formData.get('country'),
                    is_default: formData.get('is_default') === 'on'
                })
            });
            setShowAddBilling(false);
            fetchBillingAddresses();
        } catch (error) {
            alert('Failed to add billing address');
        }
    };

    const setDefaultShipping = async (id: number) => {
        try {
            await apiCall(`/api/profile/shipping-addresses/${id}/set-default`, { method: 'PUT' });
            fetchShippingAddresses();
        } catch (error) {
            alert('Failed to set default');
        }
    };

    const setDefaultBilling = async (id: number) => {
        try {
            await apiCall(`/api/profile/billing-addresses/${id}/set-default`, { method: 'PUT' });
            fetchBillingAddresses();
        } catch (error) {
            alert('Failed to set default');
        }
    };

    const deleteShipping = async (id: number) => {
        if (!confirm('Delete this address?')) return;
        try {
            await apiCall(`/api/profile/shipping-addresses/${id}`, { method: 'DELETE' });
            fetchShippingAddresses();
        } catch (error) {
            alert('Failed to delete');
        }
    };

    const deleteBilling = async (id: number) => {
        if (!confirm('Delete this address?')) return;
        try {
            await apiCall(`/api/profile/billing-addresses/${id}`, { method: 'DELETE' });
            fetchBillingAddresses();
        } catch (error) {
            alert('Failed to delete');
        }
    };

    return (
        <div className="settings-page">
            <div className="settings-header">
                <h1>Account Settings</h1>
                <p>Manage your profile, addresses, and security</p>
            </div>

            <div className="settings-tabs">
                <button className={activeTab === 'personal' ? 'active' : ''} onClick={() => setActiveTab('personal')}>
                    <User size={18} /> Personal Info
                </button>
                <button className={activeTab === 'shipping' ? 'active' : ''} onClick={() => setActiveTab('shipping')}>
                    <MapPin size={18} /> Shipping
                </button>
                <button className={activeTab === 'billing' ? 'active' : ''} onClick={() => setActiveTab('billing')}>
                    <CreditCard size={18} /> Billing
                </button>
                <button className={activeTab === 'security' ? 'active' : ''} onClick={() => setActiveTab('security')}>
                    <Shield size={18} /> Security
                </button>
            </div>

            <div className="settings-content">
                {activeTab === 'personal' && profile && (
                    <div className="settings-section">
                        <h2>Personal Information</h2>
                        <form onSubmit={handleUpdateProfile} className="settings-form">
                            <div className="form-group">
                                <label>Email (cannot be changed)</label>
                                <input type="email" value={profile.email} disabled />
                            </div>
                            <div className="form-group">
                                <label>Full Name</label>
                                <input name="full_name" defaultValue={profile.full_name} required />
                            </div>
                            <div className="form-group">
                                <label>Phone Number</label>
                                <input name="phone" type="tel" defaultValue={profile.phone} required />
                            </div>
                            <div className="form-group">
                                <label>Country</label>
                                <select name="country" defaultValue={profile.country}>
                                    <option value="US">🇺🇸 United States</option>
                                    <option value="IN">🇮🇳 India</option>
                                    <option value="GB">🇬🇧 United Kingdom</option>
                                    <option value="AE">🇦🇪 UAE</option>
                                </select>
                            </div>
                            <button type="submit" className="btn btn-primary">Save Changes</button>
                        </form>
                    </div>
                )}

                {activeTab === 'shipping' && (
                    <div className="settings-section">
                        <div className="section-header">
                            <h2>Shipping Addresses</h2>
                            <button className="btn btn-primary" onClick={() => setShowAddShipping(true)}>
                                <Plus size={16} /> Add Address
                            </button>
                        </div>
                        <div className="address-grid">
                            {shippingAddresses.map(addr => (
                                <div key={addr.id} className={`address-card ${addr.is_default ? 'default' : ''}`}>
                                    <div className="address-header">
                                        <h3>{addr.label}</h3>
                                        <div className="address-actions">
                                            {!addr.is_default && (
                                                <button onClick={() => setDefaultShipping(addr.id)} title="Set as default">
                                                    <Star size={16} />
                                                </button>
                                            )}
                                            <button onClick={() => deleteShipping(addr.id)}>
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>
                                    <div className="address-details">
                                        <p><strong>{addr.recipient_name}</strong></p>
                                        <p>{addr.address_line1}</p>
                                        {addr.address_line2 && <p>{addr.address_line2}</p>}
                                        <p>{addr.city}, {addr.state} {addr.postal_code}</p>
                                        <p>{addr.country}</p>
                                    </div>
                                    {addr.is_default === 1 && <span className="default-badge">Default</span>}
                                </div>
                            ))}
                        </div>

                        {showAddShipping && (
                            <div className="modal-overlay" onClick={() => setShowAddShipping(false)}>
                                <div className="modal-container" onClick={e => e.stopPropagation()}>
                                    <h2>Add Shipping Address</h2>
                                    <form onSubmit={handleAddShippingAddress}>
                                        <input name="label" placeholder="Label (e.g., Home, Work)" required />
                                        <input name="recipient_name" placeholder="Recipient Name" required />
                                        <input name="address_line1" placeholder="Address Line 1" required />
                                        <input name="address_line2" placeholder="Address Line 2 (optional)" />
                                        <div className="form-row">
                                            <input name="city" placeholder="City" required />
                                            <input name="state" placeholder="State" required />
                                        </div>
                                        <div className="form-row">
                                            <input name="postal_code" placeholder="ZIP Code" required />
                                            <select name="country" required>
                                                <option value="US">United States</option>
                                                <option value="IN">India</option>
                                                <option value="GB">United Kingdom</option>
                                            </select>
                                        </div>
                                        <label className="checkbox-label">
                                            <input name="is_default" type="checkbox" />
                                            Set as default shipping address
                                        </label>
                                        <div className="modal-actions">
                                            <button type="button" className="btn btn-secondary" onClick={() => setShowAddShipping(false)}>Cancel</button>
                                            <button type="submit" className="btn btn-primary">Add Address</button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'billing' && (
                    <div className="settings-section">
                        <div className="section-header">
                            <h2>Billing Addresses</h2>
                            <button className="btn btn-primary" onClick={() => setShowAddBilling(true)}>
                                <Plus size={16} /> Add Address
                            </button>
                        </div>
                        <div className="address-grid">
                            {billingAddresses.map(addr => (
                                <div key={addr.id} className={`address-card ${addr.is_default ? 'default' : ''}`}>
                                    <div className="address-header">
                                        <h3>{addr.label}</h3>
                                        <div className="address-actions">
                                            {!addr.is_default && (
                                                <button onClick={() => setDefaultBilling(addr.id)} title="Set as default">
                                                    <Star size={16} />
                                                </button>
                                            )}
                                            <button onClick={() => deleteBilling(addr.id)}>
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </div>
                                    <div className="address-details">
                                        <p><strong>{addr.full_name}</strong></p>
                                        <p>{addr.address_line1}</p>
                                        {addr.address_line2 && <p>{addr.address_line2}</p>}
                                        <p>{addr.city}, {addr.state} {addr.postal_code}</p>
                                        <p>{addr.country}</p>
                                    </div>
                                    {addr.is_default === 1 && <span className="default-badge">Default</span>}
                                </div>
                            ))}
                        </div>

                        {showAddBilling && (
                            <div className="modal-overlay" onClick={() => setShowAddBilling(false)}>
                                <div className="modal-container" onClick={e => e.stopPropagation()}>
                                    <h2>Add Billing Address</h2>
                                    <form onSubmit={handleAddBillingAddress}>
                                        <input name="label" placeholder="Label (e.g., Personal, Business)" required />
                                        <input name="full_name" placeholder="Full Name on Bill" required />
                                        <input name="address_line1" placeholder="Address Line 1" required />
                                        <input name="address_line2" placeholder="Address Line 2 (optional)" />
                                        <div className="form-row">
                                            <input name="city" placeholder="City" required />
                                            <input name="state" placeholder="State" required />
                                        </div>
                                        <div className="form-row">
                                            <input name="postal_code" placeholder="ZIP Code" required />
                                            <select name="country" required>
                                                <option value="US">United States</option>
                                                <option value="IN">India</option>
                                                <option value="GB">United Kingdom</option>
                                            </select>
                                        </div>
                                        <label className="checkbox-label">
                                            <input name="is_default" type="checkbox" />
                                            Set as default billing address
                                        </label>
                                        <div className="modal-actions">
                                            <button type="button" className="btn btn-secondary" onClick={() => setShowAddBilling(false)}>Cancel</button>
                                            <button type="submit" className="btn btn-primary">Add Address</button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'security' && (
                    <div className="settings-section">
                        <h2>Security</h2>
                        <div className="security-section">
                            <h3>Change Password</h3>
                            <p>Password reset functionality coming soon...</p>
                            <button className="btn btn-outline" disabled>Request Password Reset</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
