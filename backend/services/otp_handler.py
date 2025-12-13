"""
OTP/Password Handler for Automation
Manages prompts during checkout that require user input
"""

import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime


class OTPHandler:
    """
    Manages OTP/password prompts during automation
    
    Flow:
    1. Automation detects OTP/password field
    2. Pause automation and request input from user
    3. Send WebSocket message to frontend
    4. Wait for user response
    5. Resume automation with provided value
    """
    
    def __init__(self):
        self.pending_prompts: Dict[str, Dict] = {}
        self.active_websockets: Dict[str, any] = {}
    
    def register_websocket(self, session_id: str, websocket):
        """Register a WebSocket connection for a session"""
        self.active_websockets[session_id] = websocket
    
    def unregister_websocket(self, session_id: str):
        """Unregister a WebSocket connection"""
        if session_id in self.active_websockets:
            del self.active_websockets[session_id]
    
    async def request_input(
        self,
        session_id: str,
        prompt_type: str,
        message: str,
        field_name: str = "input"
    ) -> Optional[str]:
        """
        Request input from user (OTP, password, etc.)
        
        Args:
            session_id: Unique session identifier
            prompt_type: Type of prompt ("otp", "password", "verification")
            message: Message to display to user
            field_name: Name of the field being requested
        
        Returns:
            User's input or None if cancelled
        """
        # Create a future to wait for user response
        future = asyncio.Future()
        
        # Store pending prompt
        self.pending_prompts[session_id] = {
            "type": prompt_type,
            "message": message,
            "field_name": field_name,
            "future": future,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send WebSocket message to frontend
        await self._send_prompt_to_frontend(session_id, prompt_type, message, field_name)
        
        # Wait for user response (with timeout)
        try:
            result = await asyncio.wait_for(future, timeout=300.0)  # 5 minute timeout
            return result
        except asyncio.TimeoutError:
            print(f"[OTP Handler] Timeout waiting for {prompt_type} input")
            self.pending_prompts.pop(session_id, None)
            return None
    
    async def _send_prompt_to_frontend(
        self,
        session_id: str,
        prompt_type: str,
        message: str,
        field_name: str
    ):
        """Send prompt request to frontend via WebSocket"""
        if session_id in self.active_websockets:
            websocket = self.active_websockets[session_id]
            try:
                await websocket.send_json({
                    "type": "input_required",
                    "prompt_type": prompt_type,
                    "message": message,
                    "field_name": field_name
                })
            except Exception as e:
                print(f"[OTP Handler] Failed to send prompt to frontend: {e}")
    
    async def submit_input(self, session_id: str, value: str) -> bool:
        """
        User submitted input via frontend
        
        Args:
            session_id: Session identifier
            value: User's input
        
        Returns:
            True if successful, False if no pending prompt
        """
        if session_id not in self.pending_prompts:
            return False
        
        prompt = self.pending_prompts[session_id]
        future = prompt["future"]
        
        if not future.done():
            future.set_result(value)
        
        # Clean up
        self.pending_prompts.pop(session_id, None)
        return True
    
    async def cancel_input(self, session_id: str) -> bool:
        """
        User cancelled the input prompt
        
        Returns:
            True if successful, False if no pending prompt
        """
        if session_id not in self.pending_prompts:
            return False
        
        prompt = self.pending_prompts[session_id]
        future = prompt["future"]
        
        if not future.done():
            future.set_result(None)
        
        # Clean up
        self.pending_prompts.pop(session_id, None)
        return True
    
    def has_pending_prompt(self, session_id: str) -> bool:
        """Check if there's a pending prompt for a session"""
        return session_id in self.pending_prompts
    
    def get_pending_prompt(self, session_id: str) -> Optional[Dict]:
        """Get pending prompt details"""
        return self.pending_prompts.get(session_id)


# Global instance
otp_handler = OTPHandler()
