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
from main_orchestrator import run_full_flow

app = FastAPI(title="CHKout.ai API", version="1.0.0")

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
    return {"message": "CHKout.ai API is running", "version": "1.0.0"}

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
        # Run automation in background
        result = await run_full_flow(request.json_data)
        
        # Log full result for debugging
        print(f"[DEBUG] Automation result: {result}")
        
        return AutomationStatus(
            status="completed" if result.get("success") else "failed",
            phase=result.get("phase"),
            error=result.get("error"),
            final_url=result.get("final_url")
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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
    print("🚀 CHKout.ai API starting...")
    print(f"📍 Project root: {project_root}")
    
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
    print("👋 CHKout.ai API shutting down...")
    
    # Close all WebSocket connections
    for ws in active_websockets:
        await ws.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
