"""Browser Screenshot Service"""

import base64
import os


class ScreenshotService:
    """Captures and manages browser screenshots"""
    
    SCREENSHOT_PATH = '/tmp/chkout_screenshot.png'
    
    def __init__(self):
        self.current_screenshot = None
    
    def get_latest(self):
        """Get latest screenshot from file"""
        try:
            if os.path.exists(self.SCREENSHOT_PATH):
                with open(self.SCREENSHOT_PATH, 'rb') as f:
                    screenshot_bytes = f.read()
                    self.current_screenshot = base64.b64encode(screenshot_bytes).decode('utf-8')
                    return self.current_screenshot
        except Exception as e:
            print(f"Screenshot read error: {e}")
        return self.current_screenshot
