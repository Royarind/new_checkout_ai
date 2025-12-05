import React from 'react';
import { Package, User, MapPin } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import './InfoCards.css';

export const InfoCards: React.FC = () => {
    const { jsonData, currentState } = useAppStore();

    const task = jsonData?.tasks?.[0] || {};
    const customer = jsonData?.customer || {};

    const productInfo = {
        url: task.url || 'Not provided',
        variants: task.selectedVariant || {},
        quantity: task.quantity || 1,
    };

    const contactInfo = {
        firstName: customer.contact?.firstName || '-',
        lastName: customer.contact?.lastName || '-',
        email: customer.contact?.email || '-',
        phone: customer.contact?.phone || '-',
    };

    const addressInfo = {
        line1: customer.shippingAddress?.addressLine1 || '-',
        line2: customer.shippingAddress?.addressLine2 || '',
        city: customer.shippingAddress?.city || '-',
        province: customer.shippingAddress?.province || '-',
        postalCode: customer.shippingAddress?.postalCode || '-',
        country: customer.shippingAddress?.country || '-',
    };

    return (
        <div className="info-cards-container">
            {/* State Badge */}
            <div className="state-badge-container">
                <span className={`badge ${getStateBadgeClass(currentState)}`}>
                    {currentState.replace('NEED_', '').replace('_', ' ')}
                </span>
            </div>

            {/* Product Card */}
            <div className="info-card fade-in">
                <div className="card-header">
                    <Package size={20} />
                    <h3>Product Details</h3>
                </div>
                <div className="card-content">
                    <div className="info-row">
                        <span className="info-label">URL:</span>
                        <span className="info-value url-value" title={productInfo.url}>
                            {productInfo.url.length > 40
                                ? productInfo.url.substring(0, 40) + '...'
                                : productInfo.url}
                        </span>
                    </div>
                    {Object.keys(productInfo.variants).length > 0 && (
                        <div className="info-row">
                            <span className="info-label">Variants:</span>
                            <div className="variants-list">
                                {Object.entries(productInfo.variants).map(([key, value]) => (
                                    <span key={key} className="variant-tag">
                                        {key}: {value as string}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    <div className="info-row">
                        <span className="info-label">Quantity:</span>
                        <span className="info-value">{productInfo.quantity}</span>
                    </div>
                </div>
            </div>

            {/* Contact Card */}
            <div className="info-card fade-in">
                <div className="card-header">
                    <User size={20} />
                    <h3>Contact Information</h3>
                </div>
                <div className="card-content">
                    <div className="info-row">
                        <span className="info-label">Name:</span>
                        <span className="info-value">
                            {contactInfo.firstName} {contactInfo.lastName}
                        </span>
                    </div>
                    <div className="info-row">
                        <span className="info-label">Email:</span>
                        <span className="info-value">{contactInfo.email}</span>
                    </div>
                    <div className="info-row">
                        <span className="info-label">Phone:</span>
                        <span className="info-value">{contactInfo.phone}</span>
                    </div>
                </div>
            </div>

            {/* Address Card */}
            <div className="info-card fade-in">
                <div className="card-header">
                    <MapPin size={20} />
                    <h3>Shipping Address</h3>
                </div>
                <div className="card-content">
                    <div className="info-row">
                        <span className="info-value">{addressInfo.line1}</span>
                    </div>
                    {addressInfo.line2 && (
                        <div className="info-row">
                            <span className="info-value">{addressInfo.line2}</span>
                        </div>
                    )}
                    <div className="info-row">
                        <span className="info-value">
                            {addressInfo.city}, {addressInfo.province} {addressInfo.postalCode}
                        </span>
                    </div>
                    <div className="info-row">
                        <span className="info-value">{addressInfo.country}</span>
                    </div>
                </div>
            </div>
        </div>
    );
};

function getStateBadgeClass(state: string): string {
    if (state.includes('NEED')) return 'badge-warning';
    if (state.includes('READY')) return 'badge-success';
    return 'badge-error';
}
