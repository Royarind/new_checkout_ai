import { Link, useLocation } from 'react-router-dom';
import { Home, Wallet, Package, Settings } from 'lucide-react';
import './Navigation.css';

export const Navigation = () => {
    const location = useLocation();

    const isActive = (path: string) => location.pathname === path;

    return (
        <nav className="main-nav">
            <Link to="/" className={`nav-item ${isActive('/') ? 'active' : ''}`}>
                <Home size={20} />
                <span>Checkout</span>
            </Link>

            <Link to="/wallet" className={`nav-item ${isActive('/wallet') ? 'active' : ''}`}>
                <Wallet size={20} />
                <span>Wallet</span>
            </Link>

            <Link to="/orders" className={`nav-item ${isActive('/orders') ? 'active' : ''}`}>
                <Package size={20} />
                <span>Orders</span>
            </Link>

            <Link to="/settings" className={`nav-item ${isActive('/settings') ? 'active' : ''}`}>
                <Settings size={20} />
                <span>Settings</span>
            </Link>
        </nav>
    );
};
