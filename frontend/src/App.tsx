import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { ChatPanel } from './components/ChatPanel';
import { InfoCards } from './components/InfoCards';
import { AutomationControls } from './components/AutomationControls';
import { AutomationFlow } from './components/AutomationFlow';
import { BrowserView } from './components/BrowserView';
import { EditModal } from './components/EditModal';
import { ConfirmationModal } from './components/ConfirmationModal';
import { Wallet } from './pages/Wallet';
import { OrderHistory } from './pages/OrderHistory';
import { Settings } from './pages/Settings';
import { Auth } from './pages/Auth';
import { useAppStore } from './store/appStore';
import { useState, useEffect } from 'react';
import { Bot, Edit } from 'lucide-react';
import './App.css';

// Home/Checkout Page Component
const CheckoutPage = ({
    showEditModal,
    setShowEditModal,
    showConfirmModal,
    setShowConfirmModal,
    currentPhase,
    handleSaveEdit,
    handleConfirmStart,
    jsonData
}: any) => (
    <>
        <div className="main-grid">
            <div className="grid-left">
                <ChatPanel />
                <InfoCards />
            </div>

            <div className="grid-right">
                <BrowserView />
                <AutomationFlow currentPhase={currentPhase} />
                <AutomationControls />
            </div>
        </div>

        <EditModal
            isOpen={showEditModal}
            onClose={() => setShowEditModal(false)}
            jsonData={jsonData}
            onSave={handleSaveEdit}
        />

        <ConfirmationModal
            isOpen={showConfirmModal}
            onClose={() => setShowConfirmModal(false)}
            onConfirm={handleConfirmStart}
            jsonData={jsonData}
        />
    </>
);

function App() {
    const [showEditModal, setShowEditModal] = useState(false);
    const [showConfirmModal, setShowConfirmModal] = useState(false);
    const [currentPhase, setCurrentPhase] = useState<string | null>(null);

    const { jsonData, updateJsonData, automationRunning, setAutomationRunning, setAutomationStatus } = useAppStore();

    // Poll automation status for phase updates
    useEffect(() => {
        if (!automationRunning) return;

        const interval = setInterval(async () => {
            try {
                const response = await fetch('http://localhost:8000/api/automation/status');
                const data = await response.json();

                if (data.phase) {
                    setCurrentPhase(data.phase);
                }

                if (data.payment_ready) {
                    setAutomationStatus('✅ Payment page ready! Complete payment in browser.');
                    setAutomationRunning(false);
                }

                if (data.status === 'completed' || data.status === 'failed') {
                    setAutomationRunning(false);
                }
            } catch (error) {
                console.error('Status poll error:', error);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [automationRunning, setAutomationRunning, setAutomationStatus]);

    const handleEditClick = () => {
        setShowEditModal(true);
    };

    const handleSaveEdit = (updatedData: any) => {
        updateJsonData(updatedData);
    };

    const handleQuickCheckout = () => {
        setShowConfirmModal(true);
    };

    const handleConfirmStart = async () => {
        setShowConfirmModal(false);
        setAutomationRunning(true);
        setCurrentPhase('variant_selection');

        try {
            const response = await fetch('http://localhost:8000/api/automation/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ json_data: jsonData })
            });

            const result = await response.json();
            setAutomationStatus(
                result.status === 'completed'
                    ? `✅ Success! ${result.final_url}`
                    : `❌ Failed: ${result.error}`
            );
        } catch (error) {
            setAutomationStatus(`❌ Error: ${error}`);
        } finally {
            setAutomationRunning(false);
            setCurrentPhase(null);
        }
    };

    const isDataComplete = () => {
        const task = jsonData.tasks?.[0];
        const contact = jsonData.customer?.contact;
        const address = jsonData.customer?.shippingAddress;

        return !!(
            task?.url &&
            task?.quantity &&
            contact?.email &&
            contact?.firstName &&
            contact?.lastName &&
            address?.addressLine1 &&
            address?.city &&
            address?.province &&
            address?.postalCode
        );
    };

    return (
        <Router>
            <div className="app">
                <header className="app-header">
                    <div className="header-content">
                        <div className="logo">
                            <Bot size={32} />
                            <div>
                                <h1>
                                    <span className="logo-chk">CHK</span>
                                    <span className="logo-out">out.ai</span>
                                </h1>
                                <p className="tagline">Intelligent Checkout Automation</p>
                            </div>
                        </div>

                        <Navigation />

                        <div className="header-actions">
                            <button
                                className="btn btn-outline"
                                onClick={handleEditClick}
                                disabled={!isDataComplete()}
                            >
                                <Edit size={16} />
                                Edit Details
                            </button>
                            <button
                                className="btn btn-primary"
                                onClick={handleQuickCheckout}
                                disabled={!isDataComplete() || automationRunning}
                            >
                                {automationRunning ? '⏳ Running...' : '🚀 Quick Checkout'}
                            </button>
                        </div>
                    </div>
                </header>

                <main className="app-main">
                    <Routes>
                        <Route path="/auth" element={<Auth />} />
                        <Route path="/" element={
                            <CheckoutPage
                                showEditModal={showEditModal}
                                setShowEditModal={setShowEditModal}
                                showConfirmModal={showConfirmModal}
                                setShowConfirmModal={setShowConfirmModal}
                                currentPhase={currentPhase}
                                handleEditClick={handleEditClick}
                                handleQuickCheckout={handleQuickCheckout}
                                handleSaveEdit={handleSaveEdit}
                                handleConfirmStart={handleConfirmStart}
                                isDataComplete={isDataComplete}
                                automationRunning={automationRunning}
                                jsonData={jsonData}
                            />
                        } />
                        <Route path="/wallet" element={<Wallet />} />
                        <Route path="/orders" element={<OrderHistory />} />
                        <Route path="/settings" element={<Settings />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;
