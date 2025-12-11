"""
Progress Tracking Service
Manages real-time automation progress updates via WebSocket
"""
from typing import List, Optional
from fastapi import WebSocket
import asyncio
import json
from datetime import datetime

class ProgressTracker:
    """Singleton service for tracking automation progress"""
    
    def __init__(self):
        self.current_phase: Optional[str] = None
        self.current_step: int = 0
        self.total_steps: int = 0
        self.steps_completed: List[str] = []
        self.is_running: bool = False
        self.error: Optional[str] = None
        self.websockets: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Add a WebSocket connection"""
        await websocket.accept()
        self.websockets.append(websocket)
        
        # Send current state immediately
        await self.send_current_state(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.websockets:
            self.websockets.remove(websocket)
    
    async def send_current_state(self, websocket: WebSocket):
        """Send current progress state to a specific client"""
        state = {
            "type": "state",
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "steps_completed": self.steps_completed,
            "is_running": self.is_running,
            "error": self.error,
            "timestamp": datetime.now().isoformat()
        }
        try:
            await websocket.send_json(state)
        except:
            pass
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except:
                disconnected.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)
    
    async def update_phase(self, phase: str, step: int, total: int, message: str, details: dict = None):
        """Update current phase and broadcast to clients"""
        self.current_phase = phase
        self.current_step = step
        self.total_steps = total
        
        update = {
            "type": "progress",
            "phase": phase,
            "step": step,
            "total_steps": total,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        await self.broadcast(update)
    
    async def complete_step(self, step_name: str):
        """Mark a step as completed"""
        if step_name not in self.steps_completed:
            self.steps_completed.append(step_name)
            self.current_step += 1
            
            await self.broadcast({
                "type": "step_completed",
                "step": step_name,
                "total_completed": len(self.steps_completed),
                "timestamp": datetime.now().isoformat()
            })
    
    async def start_automation(self, total_steps: int = 10):
        """Mark automation as started"""
        self.is_running = True
        self.current_step = 0
        self.total_steps = total_steps
        self.steps_completed = []
        self.error = None
        
        await self.broadcast({
            "type": "automation_started",
            "total_steps": total_steps,
            "timestamp": datetime.now().isoformat()
        })
    
    async def complete_automation(self, success: bool = True, final_url: str = None):
        """Mark automation as completed"""
        self.is_running = False
        
        await self.broadcast({
            "type": "automation_completed",
            "success": success,
            "final_url": final_url,
            "steps_completed": len(self.steps_completed),
            "timestamp": datetime.now().isoformat()
        })
    
    async def report_error(self, error: str):
        """Report an error"""
        self.error = error
        self.is_running = False
        
        await self.broadcast({
            "type": "error",
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def reset(self):
        """Reset progress state"""
        self.current_phase = None
        self.current_step = 0
        self.total_steps = 0
        self.steps_completed = []
        self.is_running = False
        self.error = None

# Global instance
progress_tracker = ProgressTracker()
