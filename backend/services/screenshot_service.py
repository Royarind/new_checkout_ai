"""
Screenshot Service - Live Browser Screenshot Streaming
Captures screenshots every 2 seconds during automation
Streams to frontend via WebSocket
Auto-cleanup when automation stops
"""
import asyncio
import base64
import logging
import shutil
import time
from pathlib import Path
from typing import List, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Service for capturing and streaming browser screenshots"""
    
    def __init__(self):
        # Use absolute path in backend directory for consistent location
        backend_dir = Path(__file__).parent.parent
        self.screenshot_dir = backend_dir / "temp_screenshots"
        self.is_capturing = False
        self.current_screenshot_path: Optional[Path] = None
        self.websockets: List[WebSocket] = []
        self.is_locked = False

        
    async def start_capture(self, page):
        """Start capturing screenshots every 2 seconds"""
        self.is_capturing = True
        self.screenshot_dir.mkdir(exist_ok=True)
        logger.info("Screenshot capture started (2s interval)")
        
        try:
            while self.is_capturing:
                try:
                    # Generate unique filename
                    screenshot_path = self.screenshot_dir / f"screen_{int(time.time() * 1000)}.png"
                    
                    # Capture screenshot
                    await page.screenshot(path=str(screenshot_path))
                    self.current_screenshot_path = screenshot_path
                    
                    # Broadcast to all connected clients
                    await self._broadcast_screenshot()
                    
                    # Wait 2 seconds before next capture
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.debug(f"Screenshot capture error: {e}")
                    await asyncio.sleep(2)
                    
        except asyncio.CancelledError:
            logger.info("Screenshot capture cancelled")
            self.stop_capture()
    
    def stop_capture(self):
        """Stop capturing and cleanup all screenshots"""
        self.is_capturing = False
        self._cleanup_screenshots()
        logger.info("Screenshot capture stopped and cleaned up")
    
    def _cleanup_screenshots(self):
        """Delete all screenshots"""
        try:
            if self.screenshot_dir.exists():
                shutil.rmtree(self.screenshot_dir)
                logger.info(f"Deleted screenshot directory: {self.screenshot_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup screenshots: {e}")
    
    async def connect_client(self, websocket: WebSocket):
        """Add a WebSocket connection from frontend"""
        await websocket.accept()
        self.websockets.append(websocket)
        logger.info(f"Live browser client connected. Total clients: {len(self.websockets)}")
        
        # Send current state immediately
        await websocket.send_json({
            "type": "connected",
            "locked": self.is_locked
        })
        
        # Send current screenshot if available
        if self.current_screenshot_path and self.current_screenshot_path.exists():
            await self._send_screenshot(websocket, self.current_screenshot_path)
    
    def disconnect_client(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.websockets:
            self.websockets.remove(websocket)
            logger.info(f"Live browser client disconnected. Total clients: {len(self.websockets)}")
    
    async def _broadcast_screenshot(self):
        """Broadcast current screenshot to all connected clients"""
        if not self.current_screenshot_path or not self.current_screenshot_path.exists():
            return
        
        disconnected = []
        for ws in self.websockets:
            try:
                await self._send_screenshot(ws, self.current_screenshot_path)
            except Exception as e:
                logger.debug(f"Failed to send screenshot to client: {e}")
                disconnected.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_client(ws)
    
    async def _send_screenshot(self, websocket: WebSocket, screenshot_path: Path):
        """Send screenshot as base64 to a specific client"""
        try:
            # Read and encode screenshot
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Send to client
            await websocket.send_json({
                "type": "screenshot",
                "image": f"data:image/png;base64,{image_data}",
                "timestamp": time.time()
            })
        except Exception as e:
            logger.debug(f"Error sending screenshot: {e}")
            raise
    
    def lock_browser(self):
        """Lock browser to prevent user interaction during automation"""
        self.is_locked = True
        logger.info("Browser locked - automation running")
        # Broadcast lock state
        try:
            asyncio.create_task(self._broadcast_lock_state())
        except RuntimeError:
            pass
    
    def unlock_browser(self):
        """Unlock browser to allow user interaction"""
        self.is_locked = False
        logger.info("Browser unlocked - user can interact")
        # Broadcast unlock state
        try:
            asyncio.create_task(self._broadcast_lock_state())
        except RuntimeError:
            pass
    
    async def _broadcast_lock_state(self):
        """Broadcast current lock state to all connected clients"""
        message = {
            "type": "lock_state",
            "locked": self.is_locked
        }
        
        disconnected = []
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send lock state to client: {e}")
                disconnected.append(ws)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect_client(ws)


# Global instance
screenshot_service = ScreenshotService()
