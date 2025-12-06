// Quantity Dropdown Handler
async function handleQuantityDropdown(args) {
    const { targetIndex, quantity } = args;
    const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
    if (!overlay) return { success: false, reason: 'No overlay found' };

    const rect = overlay.getBoundingClientRect();
    const centerX = rect.left + (rect.width / 2);
    const centerY = rect.top + (rect.height / 2);
    const element = document.elementFromPoint(centerX, centerY);

    if (!element) return { success: false, reason: 'No element found' };

    console.log('🔽 Dropdown element:', element.tagName, element.className);

    // Handle SELECT dropdown
    if (element.tagName === 'SELECT') {
        console.log('📋 Native SELECT dropdown detected');
        for (const option of element.options) {
            if (option.value === quantity || option.text.trim() === quantity) {
                element.value = option.value;
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.dispatchEvent(new Event('input', { bubbles: true }));
                console.log('✅ Selected option:', option.text);
                return { success: true, method: 'select', value: option.value, text: option.text };
            }
        }
        return { success: false, reason: 'Option not found in select' };
    }

    // Handle custom dropdown - click to open
    console.log('🎯 Custom dropdown detected, clicking to open...');
    element.scrollIntoView({ block: 'center', behavior: 'smooth' });

    // Mark the dropdown for reference
    element.setAttribute('data-dropdown-opened', 'true');

    // Try multiple click strategies
    let clicked = false;
    try {
        element.click();
        clicked = true;
    } catch (e) {
        console.log('Direct click failed:', e.message);
        // Try dispatching click event
        element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        clicked = true;
    }

    if (clicked) {
        console.log('✅ Dropdown opened');
        return { success: true, method: 'click', needsOption: true, dropdownElement: element.className };
    }

    return { success: false, reason: 'Cannot interact with dropdown' };
}

// Quantity Option Selector
function selectQuantityOption(quantity) {
    console.log('🔍 Looking for option:', quantity);

    // Strategy 1: Look for the opened dropdown container first
    const dropdownTrigger = document.querySelector('[data-dropdown-opened="true"]');
    let searchRoot = document;

    if (dropdownTrigger) {
        console.log('📍 Found dropdown trigger, searching nearby...');
        // Look for dropdown menu near the trigger
        const parent = dropdownTrigger.closest('[class*="dropdown"], [class*="select"], [class*="menu"]');
        if (parent) {
            searchRoot = parent;
            console.log('🎯 Searching within parent container');
        }
    }

    // Common selectors for dropdown options
    const selectors = [
        '[role="option"]',
        '[role="listitem"]',
        'li[class*="option"]',
        'li[class*="item"]',
        'div[class*="option"]',
        'div[class*="item"]',
        'button[class*="option"]',
        'a[class*="option"]',
        '[data-value]',
        '.dropdown-item',
        '.select-option'
    ];

    console.log('📋 Searching with', selectors.length, 'selectors...');

    for (const selector of selectors) {
        const options = searchRoot.querySelectorAll(selector);
        console.log('  Selector', selector, ':', options.length, 'elements');

        for (const option of options) {
            // Skip if element is not visible
            const rect = option.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;

            const text = option.textContent?.trim();
            const value = option.getAttribute('data-value') || option.getAttribute('value') || option.value;

            console.log('    Checking:', text, '| value:', value);

            // Match by text or value
            if (text === quantity || value === quantity ||
                text === quantity.toString() || value === quantity.toString()) {

                console.log('✅ FOUND MATCH:', text || value);

                // Scroll option into view within its container
                option.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

                // Small delay for scroll
                setTimeout(() => {
                    console.log('🖱️ Clicking option...');

                    // Try multiple click strategies
                    try {
                        option.click();
                        console.log('✅ Click successful');
                    } catch (e) {
                        console.log('Direct click failed, trying event dispatch');
                        option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        option.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                        option.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    }
                }, 200);

                return { success: true, text: text, value: value, selector: selector };
            }
        }
    }

    console.log('❌ No matching option found');
    return { success: false, reason: 'Option not found in dropdown' };
}

// Quantity Input Handler
function handleQuantityInput(args) {
    const { targetIndex, quantity } = args;
    const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
    if (overlay) {
        const rect = overlay.getBoundingClientRect();
        const centerX = rect.left + (rect.width / 2);
        const centerY = rect.top + (rect.height / 2);
        const inputElement = document.elementFromPoint(centerX, centerY);
        if (inputElement && (inputElement.type === 'number' || inputElement.name?.includes('quantity'))) {
            // Store original value for comparison
            const originalValue = inputElement.value;

            // Set value with comprehensive event handling
            inputElement.focus();
            inputElement.value = quantity;

            // Dispatch multiple events to ensure website recognition
            const events = ['input', 'change', 'keyup', 'blur'];
            events.forEach(eventType => {
                const event = new Event(eventType, { bubbles: true, cancelable: true });
                inputElement.dispatchEvent(event);
            });

            // Wait a moment and check if value persisted
            setTimeout(() => {
                const currentValue = inputElement.value;
                console.log(`Quantity set: ${originalValue} → ${quantity}, Current: ${currentValue}`);
                if (currentValue !== quantity) {
                    console.warn(`Quantity value was reset by website: ${quantity} → ${currentValue}`);
                    // Try setting again
                    inputElement.value = quantity;
                    inputElement.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }, 500);

            return { success: true, originalValue, setTo: quantity };
        }
    }
    return { success: false };
}
