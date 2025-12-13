(args) => {
    const { val, containerSelector } = args;
    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\s]/g, '') : '';
    const normalizedVal = normalize(val);

    const match = (text) => {
        if (!text) return false;
        const t = normalize(text);

        // Exact match
        if (t === normalizedVal) return true;

        // Multi-word match: check if all words from search value exist in text
        const searchWords = normalizedVal.split(/\s+/).filter(w => w.length > 0);
        const textWords = t.split(/\s+/).filter(w => w.length > 0);

        if (searchWords.length >= 2) {
            // First try exact phrase match
            if (t.includes(normalizedVal)) {
                return true;
            }

            // Then try all words present match
            const hasAllWords = searchWords.every(word =>
                textWords.some(textWord => textWord === word || textWord.includes(word) || word.includes(textWord))
            );
            if (hasAllWords) return true;
        }

        return false;
    };

    // Clear existing overlays
    document.querySelectorAll('.automation-overlay').forEach(el => el.remove());

    // Create overlay container
    const overlayContainer = document.createElement('div');
    overlayContainer.id = 'automation-overlays';
    overlayContainer.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 999999;';
    document.body.appendChild(overlayContainer);

    let elementIndex = 0;
    const indexedElements = [];

    // Scope search to container if provided
    const root = containerSelector ? document.querySelector(containerSelector) : document;
    if (!root) return { found: false, phase: 'overlay', error: 'Container not found' };

    // Function to create overlay for element
    const createOverlay = (element, index, color = '#ff0000', label = '') => {
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return null;

        const overlay = document.createElement('div');
        overlay.className = 'automation-overlay';
        overlay.setAttribute('data-element-index', index);
        overlay.style.cssText = `
            position: absolute;
            left: ${rect.left}px;
            top: ${rect.top}px;
            width: ${rect.width}px;
            height: ${rect.height}px;
            border: 3px solid ${color};
            background: ${color}33;
            pointer-events: none;
            font-family: monospace;
            font-size: 11px;
            font-weight: bold;
            color: ${color};
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 999999;
        `;
        overlay.textContent = label || `#${index}`;
        overlayContainer.appendChild(overlay);
        return overlay;
    };

    // Index all clickable elements with overlays
    const clickableSelectors = [
        'button[name="Size"], button[name="Color"], button[name="Fit"]', // PRIORITY: Dillards Size/Color/Fit buttons
        'input[type="radio"][name*="Shade"], input[type="radio"][name*="option"], input[type="radio"][name*="Color"]',
        'input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]',
        'select[name*="quantity"], select[id*="quantity"], select[class*="quantity"]',
        'button[class*="quantity"], button[aria-label*="quantity"], button[class*="plus"], button[class*="minus"]',
        'button[name="add"], button[class*="add-to-cart"], .action--add-to-cart', // Cart buttons
        'button', 'a', 'select', 'input[type="button"]', 'input[type="submit"]',
        '[role="button"]', '[onclick]', '.clickable', '.selectable'
    ];

    // Helper to collect all elements including Shadow DOM
    const collectElements = (root, selectors) => {
        const elements = [];
        const seen = new Set();

        const traverse = (node) => {
            if (!node) return;

            // Check if node matches any selector
            if (node.matches && selectors.some(s => node.matches(s))) {
                if (!seen.has(node)) {
                    elements.push(node);
                    seen.add(node);
                }
            }

            // Traverse children
            const children = node.children || node.childNodes;
            for (const child of children) {
                traverse(child);
            }

            // Traverse Shadow DOM
            if (node.shadowRoot) {
                traverse(node.shadowRoot);
            }
        };

        traverse(root);
        return elements;
    };

    let matchedIndex = null;

    // Use deep traversal instead of simple querySelectorAll
    const allPotentialElements = collectElements(root, clickableSelectors);

    for (const element of allPotentialElements) {
        // CRITICAL: Skip elements in excluded sections (recommendations, related products, etc.)
        // This function is injected by service.py via exclusion_helper.js
        if (typeof isInExcludedSection === 'function' && isInExcludedSection(element)) {
            // Visualize excluded elements with orange overlay
            const rect = element.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                createOverlay(element, '', '#ff6600', 'EXCLUDED');
            }
            continue;
        }

        // Skip localization elements
        if (element.id === 'LocalizationForm-Select' ||
            element.classList && element.classList.contains('country-picker') ||
            element.name === 'country_code') {
            continue;
        }

        // Skip hidden or non-interactive elements
        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
        if (element.tagName === 'INPUT' && (element.type === 'hidden' || element.type === 'text' || element.type === 'search')) continue;

        const rect = element.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            const currentIndex = elementIndex++;

            // Check if this element matches our target
            let isMatch = false;
            let elementType = 'general';

            // Universal quantity detection patterns
            const ariaLabel = (element.getAttribute('aria-label') || '').toLowerCase();
            const className = (typeof element.className === 'string' ? element.className : element.className.toString()).toLowerCase();
            const elementId = (element.id || '').toLowerCase();
            const elementName = (element.name || '').toLowerCase();
            const buttonText = (element.textContent || '').trim();

            // PRIORITY 1: Cart button detection - MUST come before quantity detection
            if (normalizedVal.includes('cart') || normalizedVal.includes('add')) {
                if (element.tagName === 'BUTTON' && (
                    element.name === 'add' ||
                    element.name?.includes('add-to') ||
                    element.id?.includes('add-to') ||
                    (element.classList && element.classList.contains('add-to-cart')) ||
                    (element.classList && element.classList.contains('add-to-bag')) ||
                    buttonText.toLowerCase().includes('add to cart') ||
                    buttonText.toLowerCase().includes('add to bag') ||
                    buttonText.toLowerCase().includes('buy now') ||
                    // Match standalone "ADD" button near product area
                    (buttonText.toLowerCase().trim() === 'add' && element.type === 'submit') ||
                    (buttonText.toLowerCase() === 'add' && element.classList && element.classList.contains('product')))) {
                    elementType = 'cart_button';
                    isMatch = true;
                }
            }

            // PRIORITY 2: Quantity field detection - exclude cart buttons
            if (!isMatch && (elementName.includes('quantity') || elementName.includes('qty') ||
                elementId.includes('quantity') || elementId.includes('qty') ||
                (element.classList && element.classList.contains('quantity')) || (element.classList && element.classList.contains('qty'))) &&
                !buttonText.toLowerCase().includes('add') &&
                !buttonText.toLowerCase().includes('cart') &&
                !buttonText.toLowerCase().includes('buy') &&
                !ariaLabel.includes('add') &&
                !ariaLabel.includes('cart') &&
                !(element.classList && element.classList.contains('cart')) &&
                !(element.classList && element.classList.contains('add-to-cart'))) {

                // Only match actual form inputs, not buttons
                if (element.tagName === 'SELECT' || element.tagName === 'INPUT' ||
                    (element.tagName === 'BUTTON' && element.type !== 'submit')) {

                    // Determine actual field type
                    if (element.tagName === 'SELECT') {
                        elementType = 'quantity_dropdown';
                    } else if (element.type === 'number' || element.tagName === 'INPUT') {
                        elementType = 'quantity_input';
                    } else if (element.classList && element.classList.contains('dropdown') || element.getAttribute('role') === 'combobox') {
                        elementType = 'quantity_dropdown';
                    } else {
                        elementType = 'quantity_input'; // fallback
                    }
                    isMatch = true;
                }
            }
            // Universal quantity buttons (only if no input field found)
            else if (element.tagName === 'BUTTON' && !document.querySelector('input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]') && (
                ariaLabel.includes('increase') || ariaLabel.includes('add') || ariaLabel.includes('plus') ||
                (element.classList && element.classList.contains('plus')) || (element.classList && element.classList.contains('increase')) || (element.classList && element.classList.contains('increment')) ||
                buttonText === '+' || buttonText === '＋' || buttonText.includes('+'))) {
                elementType = 'quantity_increase';
                isMatch = true;
            }
            // Universal decrease button patterns (only if no input field found)
            else if (element.tagName === 'BUTTON' && !document.querySelector('input[type="number"], input[name*="quantity"], input[id*="quantity"], input[class*="quantity"]') && (
                ariaLabel.includes('decrease') || ariaLabel.includes('subtract') || ariaLabel.includes('minus') ||
                (element.classList && element.classList.contains('minus')) || (element.classList && element.classList.contains('decrease')) || (element.classList && element.classList.contains('decrement')) ||
                buttonText === '-' || buttonText === '－' || buttonText.includes('-'))) {
                elementType = 'quantity_decrease';
                isMatch = true;
            } else {
                // Regular text matching for other elements
                const texts = [
                    element.textContent,
                    element.value,
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.getAttribute('alt')
                ];

                // For radio buttons, also check associated label
                if (element.type === 'radio') {
                    const label = document.querySelector(`label[for="${element.id}"]`);
                    if (label) texts.push(label.textContent);
                }

                // Regular text matching (cart button already handled above)
                if (!isMatch) {
                    for (const text of texts) {
                        if (match(text)) {
                            isMatch = true;
                            break;
                        }
                    }
                }
            }

            // Create overlay (bright green for matches, yellow for candidates)
            const overlayColor = isMatch ? '#00ff00' : '#ffdd00';
            const overlayLabel = isMatch ? `✓ ${currentIndex}` : currentIndex.toString();
            createOverlay(element, currentIndex, overlayColor, overlayLabel);

            // Store element info
            indexedElements.push({
                index: currentIndex,
                element: element,
                isMatch: isMatch,
                elementType: elementType,
                text: element.textContent?.trim() || '',
                value: element.value || '',
                tagName: element.tagName,
                type: element.type || '',
                id: element.id || '',
                className: element.className || ''
            });

            if (isMatch && matchedIndex === null) {
                matchedIndex = currentIndex;
            }
        }
    }


    if (matchedIndex !== null) {
        // Determine action based on element type
        const matchedElement = indexedElements.find(el => el.index === matchedIndex);
        let action = 'click';

        if (matchedElement) {
            if (matchedElement.elementType === 'quantity_input') {
                action = 'quantity_input';
            } else if (matchedElement.elementType === 'quantity_dropdown') {
                action = 'quantity_dropdown';
            } else if (matchedElement.elementType === 'quantity_increase' || matchedElement.elementType === 'quantity_decrease') {
                action = 'quantity_button';
            } else if (matchedElement.elementType === 'cart_button') {
                action = 'click';
            }
        }

        return { found: true, action: action, elementIndex: matchedIndex, allElements: indexedElements, phase: 'overlay' };
    }

    return { found: false, phase: 'overlay' }
}
