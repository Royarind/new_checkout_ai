"""
Windows-Compatible Backend Startup Script
Fixes Playwright NotImplementedError by setting correct event loop policy BEFORE uvicorn starts
"""
import asyncio
import sys

# CRITICAL: Set Windows event loop policy BEFORE any other imports
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[OK] Windows ProactorEventLoop policy set")

import uvicorn

if __name__ == "__main__":
    print("Starting CHKout.ai Backend with Windows Playwright support...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
