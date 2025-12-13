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
# from backend.services.langchain_service import langchain_service # DELETED
# from backend.services.langchain_service import langchain_service # DELETED
# from backend.services.conversation_agent_legacy import ConversationAgent # DELETED
from backend.services.otp_handler import otp_handler
from backend.services.progress_tracker import progress_tracker
from backend.services.address_service import address_service
from backend.services.wallet_service import wallet_service
from backend.models.address import AddressCreate, AddressUpdate
from backend.models.wallet import CardCreate, UPICreate
from main_orchestrator import run_full_flow
from backend.services.screenshot_service import screenshot_service
# from backend.services.conversation_agent_legacy import LLMClient # DELETED

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
active_websockets: List[WebSocket] = []

# Pydantic models for request/response
# Chat models removed

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

# Chat endpoints removed

# Initialize Legacy Agent removed
# conversation_agent = ConversationAgent()

# ============================================
# LEGACY CHAT ENDPOINTS (Removed)
# ============================================

# @app.post("/api/chat/llm") - REMOVED
# @app.post("/api/chat/llm/reset") - REMOVED
# @app.get("/api/chat/llm/data") - REMOVED




# ============================================
# OTP HANDLER ENDPOINTS
# ============================================

@app.post("/api/otp/submit")
async def submit_otp(data: Dict[str, Any]):
    """User submitted OTP/password"""
    session_id = data.get("session_id", "default")
    value = data.get("value", "")
    
    success = await otp_handler.submit_input(session_id, value)
    if success:
        return {"message": "Input submitted successfully"}
    else:
        raise HTTPException(status_code=404, detail="No pending prompt found")

@app.post("/api/otp/cancel")
async def cancel_otp(data: Dict[str, Any]):
    """User cancelled OTP/password prompt"""
    session_id = data.get("session_id", "default")
    
    success = await otp_handler.cancel_input(session_id)
    if success:
        return {"message": "Prompt cancelled"}
    else:
        raise HTTPException(status_code=404, detail="No pending prompt found")

@app.get("/api/otp/pending/{session_id}")
async def get_pending_otp(session_id: str):
    """Get pending OTP prompt for session"""
    prompt = otp_handler.get_pending_prompt(session_id)
    if prompt:
        return prompt
    else:
        return {"has_pending": False}

# ============================================
# PRODUCT INFO ENDPOINTS
# ============================================

@app.get("/api/product/info")
async def get_product_info(url: str):
    """Get product thumbnail and info from URL"""
    try:
        from backend.services.product_scraper import extract_product_info
        info = extract_product_info(url)
        return info
    except Exception as e:
        return {
            "thumbnail": None,
            "title": None,
            "price": None,
            "error": str(e)
        }



# LLM Config endpoint removed

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
