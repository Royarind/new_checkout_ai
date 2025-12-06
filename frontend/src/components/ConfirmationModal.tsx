import React from 'react';
import { X, CheckCircle, AlertTriangle } from 'lucide-react';
import './ConfirmationModal.css';

interface ConfirmationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    jsonData: any;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
    isOpen,
    onClose,
    onConfirm,
    jsonData
}) => {
    if (!isOpen) return null;

    const task = jsonData.tasks?.[0] || {};
    const contact = jsonData.customer?.contact || {};
    const address = jsonData.customer?.shippingAddress || {};
    const variants = task.selectedVariant || {};

    const variantString = Object.entries(variants)
        .filter(([key]) => key !== '__user_specified__')
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ') || 'None';

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-container confirmation-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>Confirm Purchase Details</h2>
                    <button className="modal-close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="modal-body">
                    <div className="confirmation-section">
                        <h3>🛍️ Product Details</h3>
                        <div className="confirmation-grid">
                            <div className="confirmation-item">
                                <span className="item-label">URL:</span>
                                <span className="item-value">{task.url?.substring(0, 60)}...</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Variant:</span>
                                <span className="item-value">{variantString}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Quantity:</span>
                                <span className="item-value">{task.quantity || 1}</span>
                            </div>
                        </div>
                    </div>

                    <div className="confirmation-divider" />

                    <div className="confirmation-section">
                        <h3>👤 Contact Information</h3>
                        <div className="confirmation-grid">
                            <div className="confirmation-item">
                                <span className="item-label">Name:</span>
                                <span className="item-value">
                                    {contact.firstName} {contact.lastName}
                                </span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Email:</span>
                                <span className="item-value">{contact.email}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Phone:</span>
                                <span className="item-value">{contact.phone || 'Not provided'}</span>
                            </div>
                        </div>
                    </div>

                    <div className="confirmation-divider" />

                    <div className="confirmation-section">
                        <h3>📍 Shipping Address</h3>
                        <div className="confirmation-grid">
                            <div className="confirmation-item full-width">
                                <span className="item-label">Address:</span>
                                <span className="item-value">{address.addressLine1}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">City:</span>
                                <span className="item-value">{address.city}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">State:</span>
                                <span className="item-value">{address.province}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Postal Code:</span>
                                <span className="item-value">{address.postalCode}</span>
                            </div>
                            <div className="confirmation-item">
                                <span className="item-label">Country:</span>
                                <span className="item-value">{address.country || 'US'}</span>
                            </div>
                        </div>
                    </div>

                    <div className="confirmation-warning">
                        <AlertTriangle size={20} />
                        <span>This will start the automated checkout process immediately.</span>
                    </div>
                </div>

                <div className="modal-footer">
                    <button className="btn btn-secondary" onClick={onClose}>
                        Cancel
                    </button>
                    <button className="btn btn-success" onClick={onConfirm}>
                        <CheckCircle size={16} />
                        Confirm & Start
                    </button>
                </div>
            </div>
        </div>
    );
};
