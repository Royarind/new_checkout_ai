import asyncio
from playwright.async_api import Page

async def select_travismathew_variant(page: Page, variant: dict) -> bool:
    try:
        # Color selection
        if 'color' in variant:
            color = variant['color']
            color_input = page.locator(f'input[name="Color"][value="{color}"]')
            if await color_input.count() > 0:
                await color_input.click(force=True)
                await asyncio.sleep(0.5)
        
        # Size selection
        if 'size' in variant:
            size = variant['size']
            size_input = page.locator(f'input[name="Size"][value="{size}"]')
            if await size_input.count() > 0:
                await size_input.click(force=True)
                await asyncio.sleep(0.5)
        
        # Wait for Add to Cart button to be enabled
        add_btn = page.locator('button[name="add"]:not(.opacity-50):not([disabled])')
        await add_btn.wait_for(state='visible', timeout=5000)
        await add_btn.click()
        await asyncio.sleep(2)
        return True
    except Exception as e:
        return False
