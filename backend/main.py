"""
FastAPI Backend for CHKout.ai
Provides REST API and WebSocket endpoints for the React frontend
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import project services
from backend.services.conversation_agent import ConversationAgent
from backend.services.progress_tracker import progress_tracker
from backend.services.address_service import address_service
from backend.services.wallet_service import wallet_service
from backend.models.address import AddressCreate, AddressUpdate
from backend.models.wallet import CardCreate, UPICreate
from main_orchestrator import run_full_flow
from backend.services.screenshot_service import screenshot_service

app = FastAPI(title="CARTMIND-AI API", version="1.0.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and CRA default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
conversation_agent = ConversationAgent()
active_websockets: List[WebSocket] = []

# Pydantic models for request/response
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    ai_message: str
    json_data: Dict[str, Any]
    state: str

class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class AutomationRequest(BaseModel):
    json_data: Dict[str, Any]

class AutomationStatus(BaseModel):
    status: str
    phase: Optional[str] = None
    error: Optional[str] = None
    final_url: Optional[str] = None

# Routes
@app.get("/")
async def root():
    return {"message": "CARTMIND-AI API is running", "version": "1.0.0"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Send a message to the conversation agent and get AI response"""
    try:
        result = await conversation_agent.process_message(message.message)
        
        return ChatResponse(
            ai_message=result.get("message", result.get("ai_message", "")),
            json_data=conversation_agent.json_data,
            state=conversation_agent.state
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
async def get_chat_history():
    """Get conversation history"""
    return {"history": conversation_agent.history}

@app.post("/api/chat/reset")
async def reset_chat():
    """Reset conversation and start fresh"""
    conversation_agent.reset()
    return {"message": "Conversation reset successfully"}

@app.get("/api/config/llm", response_model=LLMConfig)
async def get_llm_config():
    """Get current LLM configuration from .env"""
    from backend.api.llm_config_api import get_session_llm_config
    
    config = get_session_llm_config()
    if not config:
        raise HTTPException(status_code=404, detail="No LLM configuration found")
    
    return LLMConfig(
        provider=config.get("provider", ""),
        model=config.get("model", ""),
        api_key="***" if config.get("api_key") else None,  # Mask API key
        base_url=config.get("base_url")
    )

@app.get("/api/data/current")
async def get_current_data():
    """Get current JSON data being built"""
    return {
        "json_data": conversation_agent.json_data,
        "state": conversation_agent.state,
        "detected_variants": conversation_agent.detected_variants
    }

@app.post("/api/automation/start")
async def start_automation(request: AutomationRequest):
    """Start the automation flow"""
    try:
        print("=== RECEIVED AUTOMATION REQUEST ===", flush=True)
        print(f"[DEBUG] Request data keys: {request.json_data.keys()}", flush=True)
        
        # Lock browser before automation
        screenshot_service.lock_browser()
        
        try:
            # Run automation in background
            result = await run_full_flow(request.json_data)
        finally:
            # Always unlock browser after automation (even if it fails)
            screenshot_service.unlock_browser()
        
        # Unlock browser on error
        screenshot_service.unlock_browser()
        
        # Log full result for debugging
        print(f"[DEBUG] Automation result: {result}")
        
        return AutomationStatus(
            status="completed" if result.get("success") else "failed",
            phase=result.get("phase"),
            error=result.get("error"),
            final_url=result.get("final_url")
        )
    except Exception as e:
        # Unlock browser on error
        screenshot_service.unlock_browser()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LIVE BROWSER SCREENSHOT STREAMING
# ============================================

@app.websocket("/ws/live-browser")
async def live_browser_websocket(websocket: WebSocket):
    """WebSocket endpoint for live browser screenshot streaming"""
    await screenshot_service.connect_client(websocket)
    try:
        # Keep connection alive and let screenshot service broadcast
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        screenshot_service.disconnect_client(websocket)
    except Exception as e:
        print(f"Live browser WebSocket error: {e}")
        screenshot_service.disconnect_client(websocket)


# ============================================
# DATA MANAGEMENT ENDPOINTS
# ============================================

@app.get("/api/data/structured")
async def get_structured_data():
    """Get structured data from current JSON"""
    json_data = conversation_agent.json_data
    
    # Extract structured sections
    product = {}
    shipping = {}
    billing = {}
    payment = {}
    
    if "tasks" in json_data and len(json_data["tasks"]) > 0:
        task = json_data["tasks"][0]
        product = {
            "url": task.get("url"),
            "name": task.get("productName"),
            "variants": task.get("variants", {}),
            "quantity": task.get("quantity", 1)
        }
    
    if "customer" in json_data:
        customer = json_data["customer"]
        if "shippingAddress" in customer:
            shipping = customer["shippingAddress"]
        if "billingAddress" in customer:
            billing = customer["billingAddress"]
        if "paymentMethod" in customer:
            payment = customer["paymentMethod"]
    
    return {
        "product": product,
        "shipping": shipping,
        "billing": billing,
        "payment": payment,
        "state": conversation_agent.state,
        "full_json": json_data
    }

@app.put("/api/data/edit")
async def edit_data(updates: Dict[str, Any]):
    """Edit specific fields in the JSON data"""
    try:
        # Deep merge updates into existing data
        def deep_update(base, updates):
            for key, value in updates.items():
                if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                    deep_update(base[key], value)
                else:
                    base[key] = value
        
        deep_update(conversation_agent.json_data, updates)
        return {"success": True, "json_data": conversation_agent.json_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/new")
async def new_session(data: Optional[Dict[str, Any]] = None):
    """Start a new session"""
    conversation_agent.reset()
    if data:
        conversation_agent.json_data = data
    return {"success": True, "message": "New session started"}

@app.post("/api/session/load-address/{address_id}")
async def load_address(address_id: str, address_type: str = "shipping"):
    """Load address from address book into session"""
    address = await address_service.get_address(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Convert to dict and add to JSON
    address_dict = {
        "fullName": address.full_name,
        "addressLine1": address.address_line1,
        "addressLine2": address.address_line2,
        "city": address.city,
        "state": address.state,
        "postalCode": address.postal_code,
        "country": address.country,
        "phone": address.phone
    }
    
    if "customer" not in conversation_agent.json_data:
        conversation_agent.json_data["customer"] = {}
    
    if address_type == "shipping":
        conversation_agent.json_data["customer"]["shippingAddress"] = address_dict
    elif address_type == "billing":
        conversation_agent.json_data["customer"]["billingAddress"] = address_dict
    
    return {"success": True, "address": address_dict}

@app.post("/api/session/load-payment/{method_id}")
async def load_payment(method_id: str):
    """Load payment method from wallet into session (decrypted)"""
    method = await wallet_service.get_payment_method(method_id, decrypt=True)
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    if "customer" not in conversation_agent.json_data:
        conversation_agent.json_data["customer"] = {}
    
    conversation_agent.json_data["customer"]["paymentMethod"] = {
        "type": method["type"],
        "data": method.get("decrypted_data", {})
    }
    
    return {"success": True, "method_type": method["type"]}

# ============================================
# ADDRESS BOOK ENDPOINTS
# ============================================

@app.post("/api/addresses")
async def create_address(address: AddressCreate):
    """Create a new address"""
    return await address_service.create_address(address)

@app.get("/api/addresses")
async def list_addresses():
    """List all addresses"""
    return await address_service.list_addresses()

@app.get("/api/addresses/{address_id}")
async def get_address(address_id: str):
    """Get a specific address"""
    address = await address_service.get_address(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address

@app.put("/api/addresses/{address_id}")
async def update_address(address_id: str, update: AddressUpdate):
    """Update an address"""
    address = await address_service.update_address(address_id, update)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address

@app.delete("/api/addresses/{address_id}")
async def delete_address(address_id: str):
    """Delete an address"""
    await address_service.delete_address(address_id)
    return {"success": True}

@app.put("/api/addresses/default/{address_id}")
async def set_default_address(address_id: str):
    """Set an address as default"""
    address = await address_service.set_default(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address

# ============================================
# WALLET ENDPOINTS
# ============================================

@app.post("/api/wallet/cards")
async def add_card(card: CardCreate):
    """Add a new card to wallet"""
    return await wallet_service.add_card(card)

@app.post("/api/wallet/upi")
async def add_upi(upi: UPICreate):
    """Add a new UPI payment method"""
    return await wallet_service.add_upi(upi)

@app.get("/api/wallet/methods")
async def list_payment_methods():
    """List all payment methods (masked)"""
    return await wallet_service.list_payment_methods()

@app.get("/api/wallet/methods/{method_id}")
async def get_payment_method(method_id: str):
    """Get a specific payment method (masked)"""
    method = await wallet_service.get_payment_method(method_id, decrypt=False)
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return method

@app.delete("/api/wallet/methods/{method_id}")
async def delete_payment_method(method_id: str):
    """Delete a payment method"""
    await wallet_service.delete_payment_method(method_id)
    return {"success": True}

@app.put("/api/wallet/default/{method_id}")
async def set_default_payment(method_id: str):
    """Set a payment method as default"""
    method = await wallet_service.set_default(method_id)
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return method

# ============================================
# WEBSOCKET ENDPOINTS
# ============================================

@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time automation progress updates"""
    await progress_tracker.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        progress_tracker.disconnect(websocket)

@app.websocket("/ws/screenshots")
async def websocket_screenshots(websocket: WebSocket):
    """WebSocket endpoint for real-time screenshot streaming"""
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            # Keep connection alive and send screenshots when available
            # This will be implemented with the screenshot service
            await asyncio.sleep(1)
            
            # Placeholder: send ping to keep connection alive
            await websocket.send_json({"type": "ping"})
            
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 CARTMIND-AI API starting...")
    print(f"📍 Project root: {project_root}")
    
    # Initialize databases
    print("📦 Initializing databases...")
    await address_service.initialize()
    await wallet_service.initialize()
    print("✅ Databases initialized")
    
    # Verify LLM configuration
    from backend.api.llm_config_api import get_session_llm_config
    config = get_session_llm_config()
    if config:
        print(f"✅ LLM configured: {config.get('provider')} - {config.get('model')}")
    else:
        print("⚠️  No LLM configuration found in .env")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("👋 CARTMIND-AI API shutting down...")
    
    # Close all WebSocket connections
    for ws in active_websockets:
        await ws.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
