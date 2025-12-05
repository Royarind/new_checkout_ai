"""
Debug script to see all form fields on checkout page
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_fields():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navigate to your checkout page and press Enter when ready...")
        input()
        
        result = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea');
                
                inputs.forEach((field, index) => {
                    if (!field.offsetParent) return;
                    
                    const label = field.closest('label') || document.querySelector(`label[for="${field.id}"]`);
                    const container = field.closest('div');
                    
                    fields.push({
                        index: index,
                        type: field.tagName.toLowerCase(),
                        name: field.name || '',
                        id: field.id || '',
                        placeholder: field.placeholder || '',
                        autocomplete: field.autocomplete || '',
                        ariaLabel: field.getAttribute('aria-label') || '',
                        labelText: label?.textContent?.trim() || '',
                        className: field.className || '',
                        value: field.value || ''
                    });
                });
                
                return fields;
            }
        """)
        
        print("\n=== ALL VISIBLE FORM FIELDS ===\n")
        for field in result:
            print(f"Field #{field['index']}:")
            print(f"  Type: {field['type']}")
            print(f"  Name: {field['name']}")
            print(f"  ID: {field['id']}")
            print(f"  Placeholder: {field['placeholder']}")
            print(f"  Autocomplete: {field['autocomplete']}")
            print(f"  Aria-label: {field['ariaLabel']}")
            print(f"  Label: {field['labelText']}")
            print(f"  Class: {field['className']}")
            print(f"  Value: {field['value']}")
            print()
        
        print(f"\nTotal fields found: {len(result)}")
        print("\nPress Enter to close browser...")
        input()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_fields())
