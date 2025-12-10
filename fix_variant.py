#!/usr/bin/env python3
"""
Fix select_variant function to parse step description instead of accepting parameters
"""

file_path = r"d:\Misc\AI Projects\checkout_ai\src\checkout_ai\agents\browser_agent.py"

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the select_variant function (around line 252-256)
new_function = '''    @BA_agent.tool_plain
    async def select_variant(current_step: str) -> str:
        """Parse and select variant from step like 'Select variant: color=Slate Grey'"""
        import re
        # Extract variant_type and variant_value from step description
        match = re.search(r'(\\w+)\\s*=\\s*([^,]+)', current_step)
        if not match:
            return "ERROR: Could not parse variant from step"
        
        variant_type = match.group(1).strip()
        variant_value = match.group(2).strip()
        
        result = await execute_tool("select_variant", variant_type=variant_type, variant_value=variant_value)
        return str(result)
'''

# Find the start of select_variant function
for i, line in enumerate(lines):
    if 'async def select_variant' in line and 'variant_type: str, variant_value: str' in line:
        # Found the function, replace it and next 3 lines
        print(f"Found select_variant at line {i+1}")
        
        # Replace lines 252-256 (indices 251-255 in 0-indexed)
        lines[i:i+4] = new_function.split('\n')[:-1]  # Split and remove last empty line
        lines[i:i+4] = [l + '\n' for l in lines[i:i+4]]  # Add newlines back
        
        print("Replaced select_variant function")
        break

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ File updated successfully!")
