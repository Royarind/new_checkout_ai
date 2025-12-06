import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import './EditModal.css';

interface EditModalProps {
    isOpen: boolean;
    onClose: () => void;
    jsonData: any;
    onSave: (data: any) => void;
}

export const EditModal: React.FC<EditModalProps> = ({ isOpen, onClose, jsonData, onSave }) => {
    const [formData, setFormData] = useState({
        quantity: 1,
        color: '',
        size: '',
        email: '',
        password: '',
        firstName: '',
        lastName: '',
        phone: '',
        address: '',
        city: '',
        province: '',
        postal: '',
        country: 'US'
    });

    useEffect(() => {
        if (isOpen && jsonData) {
            const task = jsonData.tasks?.[0] || {};
            const contact = jsonData.customer?.contact || {};
            const address = jsonData.customer?.shippingAddress || {};
            const variants = task.selectedVariant || {};

            setFormData({
                quantity: task.quantity || 1,
                color: variants.color || '',
                size: variants.size || '',
                email: contact.email || '',
                password: contact.password || '',
                firstName: contact.firstName || '',
                lastName: contact.lastName || '',
                phone: contact.phone || '',
                address: address.addressLine1 || '',
                city: address.city || '',
                province: address.province || '',
                postal: address.postalCode || '',
                country: address.country || 'US'
            });
        }
    }, [isOpen, jsonData]);

    const handleChange = (field: string, value: any) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSave = () => {
        const updatedData = {
            ...jsonData,
            tasks: [{
                ...jsonData.tasks?.[0],
                quantity: formData.quantity,
                selectedVariant: {
                    ...(formData.color && { color: formData.color }),
                    ...(formData.size && { size: formData.size })
                }
            }],
            customer: {
                ...jsonData.customer,
                contact: {
                    email: formData.email,
                    password: formData.password,
                    firstName: formData.firstName,
                    lastName: formData.lastName,
                    phone: formData.phone
                },
                shippingAddress: {
                    addressLine1: formData.address,
                    city: formData.city,
                    province: formData.province,
                    postalCode: formData.postal,
                    country: formData.country
                }
            }
        };

        onSave(updatedData);
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-container" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>Edit Checkout Details</h2>
                    <button className="modal-close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="modal-body">
                    {/* Product Details */}
                    <div className="form-section">
                        <h3>Product Details</h3>
                        <div className="form-row">
                            <div className="form-field">
                                <label>Quantity</label>
                                <input
                                    type="number"
                                    min="1"
                                    value={formData.quantity}
                                    onChange={(e) => handleChange('quantity', parseInt(e.target.value))}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-field">
                                <label>Color (optional)</label>
                                <input
                                    type="text"
                                    placeholder="e.g., Black, Blue"
                                    value={formData.color}
                                    onChange={(e) => handleChange('color', e.target.value)}
                                />
                            </div>
                            <div className="form-field">
                                <label>Size (optional)</label>
                                <input
                                    type="text"
                                    placeholder="e.g., M, L, XL"
                                    value={formData.size}
                                    onChange={(e) => handleChange('size', e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Contact Information */}
                    <div className="form-section">
                        <h3>Contact Information</h3>
                        <div className="form-row">
                            <div className="form-field full-width">
                                <label>Email *</label>
                                <input
                                    type="email"
                                    required
                                    value={formData.email}
                                    onChange={(e) => handleChange('email', e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-field">
                                <label>First Name *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.firstName}
                                    onChange={(e) => handleChange('firstName', e.target.value)}
                                />
                            </div>
                            <div className="form-field">
                                <label>Last Name *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.lastName}
                                    onChange={(e) => handleChange('lastName', e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-field">
                                <label>Phone</label>
                                <input
                                    type="tel"
                                    value={formData.phone}
                                    onChange={(e) => handleChange('phone', e.target.value)}
                                />
                            </div>
                            <div className="form-field">
                                <label>Password (if required)</label>
                                <input
                                    type="password"
                                    value={formData.password}
                                    onChange={(e) => handleChange('password', e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Shipping Address */}
                    <div className="form-section">
                        <h3>Shipping Address</h3>
                        <div className="form-row">
                            <div className="form-field full-width">
                                <label>Address Line 1 *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.address}
                                    onChange={(e) => handleChange('address', e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-field">
                                <label>City *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.city}
                                    onChange={(e) => handleChange('city', e.target.value)}
                                />
                            </div>
                            <div className="form-field">
                                <label>State/Province *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.province}
                                    onChange={(e) => handleChange('province', e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="form-row">
                            <div className="form-field">
                                <label>Postal Code *</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.postal}
                                    onChange={(e) => handleChange('postal', e.target.value)}
                                />
                            </div>
                            <div className="form-field">
                                <label>Country</label>
                                <input
                                    type="text"
                                    value={formData.country}
                                    onChange={(e) => handleChange('country', e.target.value)}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="modal-footer">
                    <button className="btn btn-secondary" onClick={onClose}>
                        Cancel
                    </button>
                    <button className="btn btn-primary" onClick={handleSave}>
                        <Save size={16} />
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
};
