"""
Loop Detection for Browser Agent

Detects when agent is stuck in infinite retry loop and triggers replanning
"""
import logging
from collections import deque
from typing import Dict, List

logger = logging.getLogger(__name__)

class LoopDetector:
    """Detect when agent is stuck in a retry loop"""
    
    def __init__(self, window_size: int = 5, threshold: int = 3):
        """
        Args:
            window_size: Number of recent actions to track
            threshold: Number of failures before triggering recovery
        """
        self.window_size = window_size
        self.threshold = threshold
        self.recent_actions = deque(maxlen=window_size)
        self.failures = 0
    
    def add_action(self, tool_name: str, success: bool, step_text: str = ""):
        """Record an action result"""
        self.recent_actions.append({
            'tool': tool_name,
            'success': success,
            'step': step_text
        })
        
        if not success:
            self.failures += 1
        else:
            # Reset on any success
            self.failures = 0
    
    def is_stuck(self) -> bool:
        """Check if agent is stuck in a loop"""
        # Too many consecutive failures
        if self.failures >= self.threshold:
            logger.warning(f"🔴 Loop detected: {self.failures} consecutive failures")
            return True
        
        # Check for repeated failed tool calls
        if len(self.recent_actions) >= self.window_size:
            failed_tools = [a['tool'] for a in self.recent_actions if not a['success']]
            
            # Same tool failing repeatedly
            if len(failed_tools) >= self.threshold and len(set(failed_tools)) == 1:
                logger.warning(f"🔴 Loop detected: '{failed_tools[0]}' failed {len(failed_tools)} times")
                return True
        
        return False
    
    def reset(self):
        """Reset detection state"""
        self.recent_actions.clear()
        self.failures = 0
    
    def get_context(self) -> str:
        """Get context for replanning"""
        recent_str = "\n".join([
            f"  - {a['tool']}: {'✓' if a['success'] else '✗'} | {a['step']}"
            for a in list(self.recent_actions)[-3:]
        ])
        
        return f"""
STUCK IN LOOP - Last 3 actions:
{recent_str}

Agent is repeatedly failing the same action and not making progress.
"""


# Export
__all__ = ['LoopDetector']
