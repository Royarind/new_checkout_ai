"""
State Manager - Saves and restores automation state
Allows resuming from failures
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

STATE_FILE = 'automation_state.json'


class StateManager:
    """Manages automation state persistence"""
    
    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_state(self, state: Dict[str, Any]):
        """Save state to file"""
        state['last_updated'] = datetime.now().isoformat()
        self.state = state
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def update_phase(self, phase: str, step: str, data: Dict[str, Any] = None):
        """Update current phase and step"""
        self.state['current_phase'] = phase
        self.state['current_step'] = step
        self.state['current_url'] = data.get('url') if data else self.state.get('current_url')
        if data:
            self.state['step_data'] = data
        self.save_state(self.state)
    
    def save_browser_state(self, cookies, storage):
        """Save browser cookies and storage"""
        self.state['cookies'] = cookies
        self.state['storage'] = storage
        self.save_state(self.state)
    
    def get_browser_state(self):
        """Get saved browser state"""
        return {
            'cookies': self.state.get('cookies', []),
            'storage': self.state.get('storage', {})
        }
    
    def mark_task_complete(self, task_index: int):
        """Mark a task as completed"""
        if 'completed_tasks' not in self.state:
            self.state['completed_tasks'] = []
        if task_index not in self.state['completed_tasks']:
            self.state['completed_tasks'].append(task_index)
        self.save_state(self.state)
    
    def get_last_completed_task(self) -> int:
        """Get index of last completed task"""
        completed = self.state.get('completed_tasks', [])
        return max(completed) if completed else -1
    
    def clear_state(self):
        """Clear saved state"""
        self.state = {}
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
    
    def get_resume_point(self) -> Dict[str, Any]:
        """Get information about where to resume"""
        return {
            'phase': self.state.get('current_phase'),
            'step': self.state.get('current_step'),
            'url': self.state.get('current_url'),
            'last_completed_task': self.get_last_completed_task(),
            'data': self.state.get('step_data', {})
        }
