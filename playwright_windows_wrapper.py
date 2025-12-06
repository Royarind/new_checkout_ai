"""
Windows-compatible wrapper for Playwright automation
Runs Playwright in a separate process with correct event loop
"""
import asyncio
import sys
import json

async def run_playwright_windows(json_data):
    """Run Playwright in subprocess on Windows to avoid event loop conflicts"""
    import subprocess
    import tempfile
    import os
    
    # Write JSON data to temp file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        json.dump(json_data, f)
        temp_file = f.name
    
    try:
        # Run main_orchestrator in subprocess with correct event loop
        script = f"""
import sys
import asyncio
import json

# Set Windows event loop policy BEFORE any async operations
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add project to path
sys.path.insert(0, r'{os.path.dirname(__file__)}')

from main_orchestrator import run_full_flow_core

# Load JSON data
with open(r'{temp_file}', 'r') as f:
    json_data = json.load(f)

# Run automation
result = asyncio.run(run_full_flow_core(json_data))

# Print result as JSON
print(json.dumps(result))
"""
        
        # Write script to temp file
        script_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py')
        script_file.write(script)
        script_file.close()
        
        # Run in subprocess
        result = subprocess.run(
            [sys.executable, script_file.name],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Clean up
        os.unlink(script_file.name)
        os.unlink(temp_file)
        
        if result.returncode == 0:
            # Parse result from stdout
            try:
                return json.loads(result.stdout.strip())
            except:
                return {"success": False, "error": f"Failed to parse result: {result.stdout}"}
        else:
            return {"success": False, "error": result.stderr}
            
    except Exception as e:
        # Clean up on error
        try:
            os.unlink(temp_file)
        except:
            pass
        return {"success": False, "error": str(e)}
