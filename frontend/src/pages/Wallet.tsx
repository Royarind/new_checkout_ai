import { useState, useEffect } from 'react';
import { CreditCard, Trash2, Plus, CheckCircle } from 'lucide-react';
import { apiCall } from '../hooks/useAuth';
import './Wallet.css';

interface PaymentMethod {
    id: number;
    label: string;
    payment_type: 'card' | 'upi' | 'paypal';
    is_default: number;
    card_number?: string;
    card_brand?: string;
    upi_id?: string;
    paypal_email?: string;
}

export const Wallet = () => {
    const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
    const [showAddCard, setShowAddCard] = useState(false);
    const [showAddUPI, setShowAddUPI] = useState(false);

    useEffect(() => {
        fetchPaymentMethods();
    }, []);

    const fetchPaymentMethods = async () => {
        try {
            const response = await apiCall('/api/wallet/payment-methods');
            const data = await response.json();
            setPaymentMethods(data);
        } catch (error) {
            console.error('Failed to fetch payment methods:', error);
        }
    };

    const handleAddCard = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        try {
            await apiCall('/api/wallet/add-card', {
                method: 'POST',
                body: JSON.stringify({
                    label: formData.get('label'),
                    card_number: formData.get('card_number'),
                    card_holder_name: formData.get('card_holder_name'),
                    expiry_month: parseInt(formData.get('expiry_month') as string),
                    expiry_year: parseInt(formData.get('expiry_year') as string),
                    cvv: formData.get('cvv'),
                    card_brand: formData.get('card_brand')
                })
            });

            setShowAddCard(false);
            fetchPaymentMethods();
        } catch (error) {
            console.error('Failed to add card:', error);
        }
    };

    const handleAddUPI = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        try {
            await apiCall('/api/wallet/add-upi', {
                method: 'POST',
                body: JSON.stringify({
                    label: formData.get('label'),
                    upi_id: formData.get('upi_id')
                })
            });

            setShowAddUPI(false);
            fetchPaymentMethods();
        } catch (error) {
            console.error('Failed to add UPI:', error);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Delete this payment method?')) return;

        try {
            await apiCall(`/api/wallet/payment-methods/${id}`, {
                method: 'DELETE'
            });
            fetchPaymentMethods();
        } catch (error) {
            console.error('Failed to delete:', error);
        }
    };

    return (
        <div className="wallet-page">
            <div className="wallet-header">
                <h1>Payment Wallet</h1>
                <div className="add-buttons">
                    <button className="btn btn-primary" onClick={() => setShowAddCard(true)}>
                        <Plus size={16} /> Add Card
                    </button>
                    <button className="btn btn-outline" onClick={() => setShowAddUPI(true)}>
                        <Plus size={16} /> Add UPI
                    </button>
                </div>
            </div>

            <div className="payment-methods-grid">
                {paymentMethods.map(pm => (
                    <div key={pm.id} className={`payment-card ${pm.is_default ? 'default' : ''}`}>
                        <div className="card-header">
                            <CreditCard size={24} />
                            <button className="delete-btn" onClick={() => handleDelete(pm.id)}>
                                <Trash2 size={16} />
                            </button>
                        </div>

                        <h3>{pm.label}</h3>

                        {pm.payment_type === 'card' && (
                            <div className="card-details">
                                <p className="card-number">•••• {pm.card_number?.slice(-4)}</p>
                                <p className="card-brand">{pm.card_brand?.toUpperCase()}</p>
                            </div>
                        )}

                        {pm.payment_type === 'upi' && (
                            <div className="card-details">
                                <p className="upi-id">{pm.upi_id}</p>
                            </div>
                        )}

                        {pm.is_default === 1 && (
                            <div className="default-badge">
                                <CheckCircle size={14} /> Default
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Add Card Modal */}
            {showAddCard && (
                <div className="modal-overlay" onClick={() => setShowAddCard(false)}>
                    <div className="modal-container" onClick={e => e.stopPropagation()}>
                        <h2>Add Credit/Debit Card</h2>
                        <form onSubmit={handleAddCard}>
                            <input name="label" placeholder="Card Label (e.g., Personal Visa)" required />
                            <input name="card_number" placeholder="Card Number" required />
                            <input name="card_holder_name" placeholder="Cardholder Name" required />
                            <div className="form-row">
                                <input name="expiry_month" type="number" placeholder="MM" min="1" max="12" required />
                                <input name="expiry_year" type="number" placeholder="YYYY" required />
                            </div>
                            <input name="cvv" type="password" placeholder="CVV" required />
                            <select name="card_brand">
                                <option value="visa">Visa</option>
                                <option value="mastercard">Mastercard</option>
                                <option value="amex">Amex</option>
                            </select>
                            <div className="modal-actions">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowAddCard(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary">Add Card</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Add UPI Modal */}
            {showAddUPI && (
                <div className="modal-overlay" onClick={() => setShowAddUPI(false)}>
                    <div className="modal-container" onClick={e => e.stopPropagation()}>
                        <h2>Add UPI ID</h2>
                        <form onSubmit={handleAddUPI}>
                            <input name="label" placeholder="Label (e.g., My PhonePe)" required />
                            <input name="upi_id" placeholder="UPI ID (e.g., user@paytm)" required />
                            <div className="modal-actions">
                                <button type="button" className="btn btn-secondary" onClick={() => setShowAddUPI(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary">Add UPI</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};
