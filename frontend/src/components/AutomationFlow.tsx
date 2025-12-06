import React from 'react';
import { Check, Loader2 } from 'lucide-react';
import './AutomationFlow.css';

export interface FlowPhase {
    id: string;
    label: string;
    status: 'pending' | 'active' | 'completed' | 'error';
}

interface AutomationFlowProps {
    currentPhase: string | null;
}

const FLOW_PHASES: FlowPhase[] = [
    { id: 'variant_selection', label: 'Variant Selection', status: 'pending' },
    { id: 'quantity_selection', label: 'Quantity Selection', status: 'pending' },
    { id: 'add_to_cart', label: 'Add to Cart', status: 'pending' },
    { id: 'navigate_cart', label: 'Navigate to Cart', status: 'pending' },
    { id: 'checkout', label: 'Go to Checkout', status: 'pending' },
    { id: 'contact_info', label: 'Contact Info', status: 'pending' },
    { id: 'shipping_address', label: 'Shipping Address', status: 'pending' },
    { id: 'shipping_method', label: 'Shipping Method', status: 'pending' },
    { id: 'payment_fill', label: 'Fill Payment', status: 'pending' },
    { id: 'payment_submit', label: 'Place Order', status: 'pending' },
    { id: 'order_confirmation', label: 'Order Confirmed', status: 'pending' },
];

export const AutomationFlow: React.FC<AutomationFlowProps> = ({ currentPhase }) => {
    const getPhaseStatus = (_phase: FlowPhase, index: number): FlowPhase['status'] => {
        if (!currentPhase) return 'pending';

        const currentIndex = FLOW_PHASES.findIndex(p => p.id === currentPhase);

        if (index < currentIndex) return 'completed';
        if (index === currentIndex) return 'active';
        return 'pending';
    };

    return (
        <div className="automation-flow">
            <div className="flow-header">
                <h3>Automation Progress</h3>
            </div>

            <div className="flow-timeline">
                {FLOW_PHASES.map((phase, index) => {
                    const status = getPhaseStatus(phase, index);
                    const isLast = index === FLOW_PHASES.length - 1;

                    return (
                        <div key={phase.id} className="flow-step-container">
                            <div className={`flow-step flow-step-${status}`}>
                                <div className="step-indicator">
                                    {status === 'completed' && (
                                        <div className="step-icon step-icon-completed">
                                            <Check size={16} strokeWidth={3} />
                                        </div>
                                    )}
                                    {status === 'active' && (
                                        <div className="step-icon step-icon-active">
                                            <Loader2 size={16} className="icon-spin" />
                                        </div>
                                    )}
                                    {status === 'pending' && (
                                        <div className="step-icon step-icon-pending">
                                            {index + 1}
                                        </div>
                                    )}
                                    {status === 'error' && (
                                        <div className="step-icon step-icon-error">
                                            ✕
                                        </div>
                                    )}
                                </div>

                                <div className="step-content">
                                    <div className={`step-label step-label-${status}`}>
                                        {phase.label}
                                    </div>
                                    {status === 'active' && (
                                        <div className="step-status">In Progress...</div>
                                    )}
                                    {status === 'completed' && (
                                        <div className="step-status step-status-completed">✓ Done</div>
                                    )}
                                </div>
                            </div>

                            {!isLast && (
                                <div className={`flow-connector flow-connector-${status === 'completed' ? 'completed' : 'pending'}`}>
                                    <div className="connector-line" />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
