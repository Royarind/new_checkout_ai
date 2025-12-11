"""
CDP Service - Chrome DevTools Protocol Proxy
Manages WebSocket connections between frontend and Chrome CDP endpoint
Handles browser lock/unlock state during automation
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import WebSocket
import aiohttp

logger = logging.getLogger(__name__)


class CDPService:
    """Singleton service for managing CDP connections and browser lock state"""
    
    def __init__(self):
        self.cdp_endpoint: Optional[str] = None
        self.is_locked: bool = False
        self.websockets: List[WebSocket] = []
        self.cdp_session: Optional[aiohttp.ClientWebSocketResponse] = None
        self.browser_url: str = "about:blank"
        
    def set_cdp_endpoint(self, endpoint: str):
        """Set the CDP WebSocket endpoint URL"""
        self.cdp_endpoint = endpoint
        logger.info(f"CDP endpoint set: {endpoint}")
    
    def lock_browser(self):
        """Lock browser to prevent user interaction during automation"""
        self.is_locked = True
        logger.info("Browser locked - automation running")
        # Broadcast lock state to all connected clients (if event loop exists)
        try:
            asyncio.create_task(self._broadcast_lock_state())
        except RuntimeError:
            # No event loop running, skip broadcast
            pass
    
    def unlock_browser(self):
        """Unlock browser to allow user interaction"""
        self.is_locked = False
        logger.info("Browser unlocked - user can interact")
        # Broadcast unlock state to all connected clients (if event loop exists)
        try:
            asyncio.create_task(self._broadcast_lock_state())
        except RuntimeError:
            # No event loop running, skip broadcast
            pass

    
    async def _broadcast_lock_state(self):
        """Broadcast current lock state to all connected clients"""
        message = {
            "type": "lock_state",
            "locked": self.is_locked
        }
        await self._broadcast(message)
    
    async def connect_client(self, websocket: WebSocket):
        """Add a WebSocket connection from frontend"""
        await websocket.accept()
        self.websockets.append(websocket)
        logger.info(f"CDP client connected. Total clients: {len(self.websockets)}")
        
        # Send current state immediately
        await websocket.send_json({
            "type": "connected",
            "cdp_endpoint": self.cdp_endpoint,
            "locked": self.is_locked,
            "browser_url": self.browser_url
        })
    
    def disconnect_client(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.websockets:
            self.websockets.remove(websocket)
            logger.info(f"CDP client disconnected. Total clients: {len(self.websockets)}")
    
    async def _broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to client: {e}")
                disconnected.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_client(ws)
    
    async def forward_cdp_message(self, websocket: WebSocket, message: dict):
        """
        Forward CDP message from frontend to Chrome
        Blocks user interaction commands when browser is locked
        """
        # Check if message is a user interaction command
        method = message.get("method", "")
        
        # Block user interaction commands when locked
        if self.is_locked and self._is_user_interaction(method):
            logger.debug(f"Blocked user interaction command while locked: {method}")
            await websocket.send_json({
                "id": message.get("id"),
                "error": {
                    "code": -32000,
                    "message": "Browser is locked during automation"
                }
            })
            return
        
        # Forward message to Chrome CDP (this will be implemented when we have CDP connection)
        # For now, just log it
        logger.debug(f"Forwarding CDP command: {method}")
    
    def _is_user_interaction(self, method: str) -> bool:
        """Check if CDP method is a user interaction command"""
        interaction_methods = [
            "Input.dispatchMouseEvent",
            "Input.dispatchKeyEvent",
            "Input.dispatchTouchEvent",
            "Input.insertText",
            "Page.navigate",
            "Runtime.evaluate"  # Could be used for interaction
        ]
        return method in interaction_methods
    
    def update_browser_url(self, url: str):
        """Update current browser URL and broadcast to clients"""
        self.browser_url = url
        try:
            asyncio.create_task(self._broadcast({
                "type": "url_update",
                "url": url
            }))
        except RuntimeError:
            # No event loop running, skip broadcast
            pass

    
    def get_status(self) -> Dict[str, Any]:
        """Get current CDP service status"""
        return {
            "cdp_endpoint": self.cdp_endpoint,
            "is_locked": self.is_locked,
            "connected_clients": len(self.websockets),
            "browser_url": self.browser_url
        }


# Global instance
cdp_service = CDPService()
