import { useState, useEffect } from 'react';
import { Package, ExternalLink, Calendar, DollarSign } from 'lucide-react';
import { apiCall } from '../hooks/useAuth';
import './OrderHistory.css';

interface Order {
    id: number;
    order_number: string;
    site_domain: string;
    site_name: string;
    order_url: string;
    total_amount: number;
    currency: string;
    status: string;
    category: string;
    ordered_at: string;
}

export const OrderHistory = () => {
    const [orders, setOrders] = useState<Order[]>([]);
    const [filter, setFilter] = useState<string>('all');

    useEffect(() => {
        fetchOrders();
    }, []);

    const fetchOrders = async () => {
        try {
            const response = await apiCall('/api/orders');
            const data = await response.json();
            setOrders(data);
        } catch (error) {
            console.error('Failed to fetch orders:', error);
        }
    };

    const filteredOrders = filter === 'all'
        ? orders
        : orders.filter(o => o.category === filter);

    const categories = [...new Set(orders.map(o => o.category).filter(Boolean))];

    return (
        <div className="order-history-page">
            <div className="orders-header">
                <h1>Order History</h1>

                <div className="filters">
                    <button
                        className={filter === 'all' ? 'active' : ''}
                        onClick={() => setFilter('all')}
                    >
                        All Orders
                    </button>
                    {categories.map(cat => (
                        <button
                            key={cat}
                            className={filter === cat ? 'active' : ''}
                            onClick={() => setFilter(cat)}
                        >
                            {cat}
                        </button>
                    ))}
                </div>
            </div>

            <div className="orders-list">
                {filteredOrders.length === 0 ? (
                    <div className="empty-state">
                        <Package size={64} />
                        <p>No orders yet</p>
                        <span>Your completed purchases will appear here</span>
                    </div>
                ) : (
                    filteredOrders.map(order => (
                        <div key={order.id} className="order-card">
                            <div className="order-header">
                                <div className="order-info">
                                    <h3>{order.site_name || order.site_domain}</h3>
                                    <span className="order-number">Order #{order.order_number}</span>
                                </div>

                                <div className="order-meta">
                                    <span className={`status-badge ${order.status}`}>
                                        {order.status}
                                    </span>
                                    {order.category && (
                                        <span className="category-badge">{order.category}</span>
                                    )}
                                </div>
                            </div>

                            <div className="order-details">
                                <div className="detail-item">
                                    <Calendar size={16} />
                                    <span>{new Date(order.ordered_at).toLocaleDateString()}</span>
                                </div>

                                {order.total_amount > 0 && (
                                    <div className="detail-item">
                                        <DollarSign size={16} />
                                        <span>{order.currency} {order.total_amount.toFixed(2)}</span>
                                    </div>
                                )}

                                {order.order_url && (
                                    <a
                                        href={order.order_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="view-order-link"
                                    >
                                        <ExternalLink size={16} />
                                        View Order
                                    </a>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
