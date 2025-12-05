import { ChatPanel } from './components/ChatPanel';
import { InfoCards } from './components/InfoCards';
import { AutomationControls } from './components/AutomationControls';
import { Bot } from 'lucide-react';
import './App.css';

function App() {
    return (
        <div className="app">
            <header className="app-header">
                <div className="header-content">
                    <div className="logo">
                        <Bot size={32} />
                        <h1>CHKout.ai</h1>
                    </div>
                    <p className="tagline">Intelligent Checkout Automation</p>
                </div>
            </header>

            <main className="app-main">
                <div className="main-grid">
                    {/* Left Column - Chat */}
                    <div className="grid-chat">
                        <ChatPanel />
                    </div>

                    {/* Right Column - Info & Controls */}
                    <div className="grid-sidebar">
                        <div className="sidebar-top">
                            <InfoCards />
                        </div>
                        <div className="sidebar-bottom">
                            <AutomationControls />
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default App;
