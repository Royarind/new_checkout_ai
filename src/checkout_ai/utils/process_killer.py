#!/usr/bin/env python3

import os
import sys
import signal
import psutil
import asyncio
from playwright.async_api import Page, Browser

async def kill_automation_process(browser: Browser = None, page: Page = None, force: bool = False):
    """Kill the automation process and cleanup resources"""
    
    try:
        # Close browser resources gracefully
        if page and not page.is_closed():
            await page.close()
        
        if browser:
            await browser.close()
            
    except Exception as e:
        print(f"Error during graceful cleanup: {e}")
    
    if force:
        # Force kill all Chrome/Chromium processes
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'chrom' in proc.info['name'].lower():
                    proc.kill()
        except Exception as e:
            print(f"Error killing Chrome processes: {e}")
    
    # Exit the Python process
    os._exit(0)

def emergency_kill():
    """Emergency kill - immediately terminate the process"""
    os.kill(os.getpid(), signal.SIGTERM)