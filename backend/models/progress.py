from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ProgressUpdate(BaseModel):
    """Progress update model for automation tracking"""
    type: str = "progress"
    phase: str  # e.g., "navigating", "selecting_variant", "adding_to_cart"
    step: int
    total_steps: int
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = datetime.now().isoformat()

class ProgressState(BaseModel):
    """Current state of automation progress"""
    current_phase: Optional[str] = None
    current_step: int = 0
    total_steps: int = 0
    steps_completed: list[str] = []
    is_running: bool = False
    error: Optional[str] = None
