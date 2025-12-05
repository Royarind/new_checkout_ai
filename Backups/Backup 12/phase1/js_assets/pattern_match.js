(val) => {
    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\s]/g, '') : '';
    const normalizedVal = normalize(val);

    const match = (text) => {
        if (!text) return false;
        const t = normalize(text);

        // Exact match
        if (t === normalizedVal) return true;

        // Multi-word match
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

    // Clear markers
    document.querySelectorAll('[data-dom-el]').forEach(el => el.removeAttribute('data-dom-el'));
    const skipElements = new Set(document.querySelectorAll('[data-already-selected]'));

    // Universal search patterns
    const searchPatterns = [
        // Native SELECT dropdowns (highest priority for size/variant selection)
        {
            selector: 'select', action: 'select',
            extraCheck: (el) => {
                // Skip localization/country selects
                if (el.id === 'LocalizationForm-Select' || el.name === 'country_code') return false;

                // Check if any option matches
                for (const option of el.options) {
                    if (match(option.text) || match(option.value)) {
                        return true;
                    }
                }
                return false;
            }
        },

        // Size radio buttons (specific pattern for Hollister/A&F)
        {
            selector: 'input[name="pdp_size-primary"], input[name="pdp_size-secondary"]', action: 'click',
            extraCheck: (el) => {
                const label = document.querySelector(`label[for="${el.id}"]`);
                const labelText = label?.querySelector('.sitg-label-text')?.textContent;
                if (match(labelText) || match(el.value) || match(el.getAttribute('aria-label'))) return true;

                // Check label's title and children's title
                if (label) {
                    if (match(label.getAttribute('title'))) return true;
                    const childrenWithTitle = label.querySelectorAll('[title]');
                    for (const child of childrenWithTitle) {
                        if (match(child.getAttribute('title'))) return true;
                    }
                }
                return false;
            }
        },

        // Dropdowns and comboboxes (including Vue Select) - only if they contain the search value
        {
            selector: '.v-select, .vs__dropdown-toggle, .vs__selected-options, .dropdown, [role="combobox"], select, [class*="dropdown"], [class*="select"]', action: 'dropdown',
            extraCheck: (el) => {
                // Skip quantity, size, and other non-matching dropdowns
                if ((el.classList && el.classList.contains('quantity')) || el.closest('.quantity-selector')) {
                    return false;
                }
                const excludePatterns = ['country', 'localization', 'currency', 'language', 'region', 'shipping', 'search', 'filter', 'sort', 'size'];
                const elementInfo = (el.id + ' ' + el.className + ' ' + (el.name || '') + ' ' + (el.textContent || '')).toLowerCase();
                if (excludePatterns.some(pattern => elementInfo.includes(pattern))) {
                    return false;
                }
                // Only match if dropdown actually contains the search value
                const dropdownTexts = [
                    el.textContent,
                    el.value,
                    el.getAttribute('aria-label'),
                    el.getAttribute('title')
                ];
                return dropdownTexts.some(text => match(text));
            }
        },

        // Labels containing radio buttons or checkboxes (size buttons, etc.)
        {
            selector: 'label', action: 'click',
            extraCheck: (el) => {
                // Check if label contains input OR points to input via 'for'
                let input = el.querySelector('input[type="radio"], input[type="checkbox"]');
                if (!input && el.getAttribute('for')) {
                    input = document.getElementById(el.getAttribute('for'));
                }
                if (!input || (input.type !== 'radio' && input.type !== 'checkbox')) return false;

                // Check label text content
                if (match(el.textContent)) return true;

                // Check label's title attribute
                if (match(el.getAttribute('title'))) return true;

                // Check all child elements' title attributes
                const childrenWithTitle = el.querySelectorAll('[title]');
                for (const child of childrenWithTitle) {
                    if (match(child.getAttribute('title'))) return true;
                }

                // Check the input value and attributes
                if (match(input.value) || match(input.getAttribute('aria-label'))) return true;

                // Check associated images for color swatches
                const parentSection = el.closest('section');
                const img = parentSection?.querySelector('img');
                if (img && match(img.alt)) return true;

                return false;
            }
        },

        // Fallback for standalone radio/checkbox inputs
        {
            selector: 'input[type="radio"], input[type="checkbox"]', action: 'click',
            extraCheck: (el) => {
                // Skip if already handled by parent label
                if (el.closest('label')) return false;

                // Check input's own attributes first
                if (match(el.value) || match(el.getAttribute('aria-label'))) return true;

                // Check associated label via 'for' attribute
                const label = document.querySelector(`label[for="${el.id}"]`);
                if (label) {
                    if (match(label.textContent)) return true;
                    if (match(label.getAttribute('title'))) return true;

                    // Check label's children with title
                    const childrenWithTitle = label.querySelectorAll('[title]');
                    for (const child of childrenWithTitle) {
                        if (match(child.getAttribute('title'))) return true;
                    }
                }

                // Check images in parent section
                const parentSection = el.closest('section');
                const img = parentSection?.querySelector('img');
                if (img && match(img.alt)) return true;

                return false;
            }
        },

        // Universal element traversal (images, labels, spans, divs)
        {
            selector: 'img, label, span, div, li, td, a', action: 'click',
            extraCheck: (el) => {
                // Check if current element matches
                const elementTexts = [
                    el.textContent?.trim(),
                    el.alt,
                    el.getAttribute('aria-label'),
                    el.getAttribute('title'),
                    el.getAttribute('data-value'),
                    el.value
                ];

                const hasMatch = elementTexts.some(text => match(text));
                if (!hasMatch) return false;

                // Universal traversal to find best clickable element

                // Priority 1: Check if element is inside a label with 'for' attribute
                let labelParent = el.closest('label[for]');
                if (labelParent) {
                    const targetInput = document.getElementById(labelParent.getAttribute('for'));
                    if (targetInput && (targetInput.type === 'radio' || targetInput.type === 'checkbox')) {
                        targetInput.setAttribute('data-dom-el', 'true');
                        return false;
                    }
                }

                // Priority 2: Look for associated radio/checkbox by traversing up and down
                let current = el;
                let attempts = 0;

                while (current && attempts < 10) {
                    // Look for radio/checkbox inputs in current container
                    const inputs = current.querySelectorAll ? current.querySelectorAll('input[type="radio"], input[type="checkbox"]') : [];
                    for (const input of inputs) {
                        if (input.offsetParent !== null) {
                            input.setAttribute('data-dom-el', 'true');
                            return false;
                        }
                    }

                    // Look for labels with 'for' attribute in current container
                    const labels = current.querySelectorAll ? current.querySelectorAll('label[for]') : [];
                    for (const label of labels) {
                        const targetInput = document.getElementById(label.getAttribute('for'));
                        if (targetInput && (targetInput.type === 'radio' || targetInput.type === 'checkbox')) {
                            targetInput.setAttribute('data-dom-el', 'true');
                            return false;
                        }
                    }

                    // Look for buttons
                    const buttons = current.querySelectorAll ? current.querySelectorAll('button') : [];
                    for (const button of buttons) {
                        if (button.offsetParent !== null) {
                            button.setAttribute('data-dom-el', 'true');
                            return false;
                        }
                    }

                    // Check if current element itself is clickable
                    const isClickable = current.onclick ||
                        current.getAttribute('onclick') ||
                        current.style.cursor === 'pointer' ||
                        (current.classList && current.classList.contains('clickable')) ||
                        (current.classList && current.classList.contains('selectable')) ||
                        current.hasAttribute('role');

                    if (isClickable && current.offsetParent !== null) {
                        current.setAttribute('data-dom-el', 'true');
                        return false;
                    }

                    // Move to parent and continue traversal
                    current = current.parentElement;
                    attempts++;
                }

                // If no better element found, use original element
                return true;
            }
        },

        // Quantity inputs
        {
            selector: 'input[type="number"], input[type="text"], input:not([type])', action: 'quantity_input',
            extraCheck: (el) => {
                const name = (el.name || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const className = (el.className || '').toLowerCase();
                return name.includes('quantity') || name.includes('qty') ||
                    id.includes('quantity') || id.includes('qty') ||
                    (el.classList && el.classList.contains('quantity')) || (el.classList && el.classList.contains('qty'));
            }
        },

        // Quantity buttons
        {
            selector: 'button, [role="button"]', action: 'quantity_button',
            extraCheck: (el) => {
                const text = (el.textContent || '').trim();
                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                const className = (el.className || '').toLowerCase();
                return text === '+' || text === '-' || text === '＋' || text === '－' ||
                    ariaLabel.includes('increase') || ariaLabel.includes('decrease') ||
                    ariaLabel.includes('plus') || ariaLabel.includes('minus') ||
                    (el.classList && el.classList.contains('quantity')) && ((el.classList && el.classList.contains('plus')) || (el.classList && el.classList.contains('minus')) || (el.classList && el.classList.contains('increment')) || (el.classList && el.classList.contains('decrement')));
            }
        },

        // Buttons
        {
            selector: 'button, [role="button"]', action: 'click',
            extraCheck: (el) => match(el.textContent) || match(el.getAttribute('aria-label')) ||
                match(el.value) || match(el.getAttribute('title'))
        },

        // Color swatch links (specific for Lulus-style swatches)
        {
            selector: 'a[aria-label*="Change selection to"], a[aria-label*="Current selection"]', action: 'click',
            extraCheck: (el) => {
                const ariaLabel = el.getAttribute('aria-label') || '';
                // Extract color name from aria-label like "Change selection to Beige"
                const colorMatch = ariaLabel.match(/(?:Change selection to|Current selection:)\s+(.+)/);
                if (colorMatch && colorMatch[1]) {
                    return match(colorMatch[1]);
                }
                return match(ariaLabel);
            }
        },

        // Links and clickable elements
        {
            selector: 'a, [onclick], [class*="clickable"], [class*="selectable"]', action: 'click',
            extraCheck: (el) => match(el.textContent) || match(el.getAttribute('aria-label'))
        },

        // Color swatches and images
        {
            selector: 'a[class*="swatch"], img[alt*="Beige"], img[alt*="Black"], img[alt*="White"], img[alt*="Red"], img[alt*="Blue"], img[alt*="Green"], img[alt*="Brown"], img[alt*="Gray"], img[alt*="Pink"], img[alt*="Purple"], img[alt*="Yellow"], img[alt*="Orange"], [class*="swatch"], [class*="color"]', action: 'click',
            extraCheck: (el) => {
                // Check element itself
                if (match(el.alt) || match(el.getAttribute('title')) ||
                    match(el.getAttribute('data-color')) || match(el.getAttribute('data-value')) ||
                    match(el.getAttribute('aria-label'))) return true;

                // Check parent link for aria-label
                const parentLink = el.closest('a');
                if (parentLink && match(parentLink.getAttribute('aria-label'))) return true;

                // Check child images
                const childImg = el.querySelector('img');
                if (childImg && (match(childImg.alt) || match(childImg.getAttribute('aria-label')))) return true;

                return false;
            }
        },

        // Generic clickable elements with data attributes
        {
            selector: '[data-caption], [data-value], [data-option], [data-variant], [data-size], [data-color]', action: 'click',
            extraCheck: (el) => {
                const dataAttrs = ['data-caption', 'data-value', 'data-option', 'data-variant', 'data-size', 'data-color'];
                return dataAttrs.some(attr => match(el.getAttribute(attr)));
            }
        },

        // Text elements
        {
            selector: 'span, div, label, li, td', action: 'click',
            extraCheck: (el) => {
                const text = el.textContent?.trim();
                return text && text.length < 100 && match(text) &&
                    (el.onclick || el.getAttribute('onclick') ||
                        el.style.cursor === 'pointer' ||
                        (el.classList && el.classList.contains('clickable')) ||
                        (el.classList && el.classList.contains('selectable')));
            }
        }
    ];

    // Search through patterns
    for (const pattern of searchPatterns) {
        const elements = document.querySelectorAll(pattern.selector);
        for (const el of elements) {
            if (skipElements.has(el)) continue;

            let isMatch = false;
            if (pattern.extraCheck) {
                isMatch = pattern.extraCheck(el);
            } else {
                isMatch = match(el.textContent) || match(el.value) || match(el.getAttribute('aria-label'));
            }

            if (isMatch) {
                el.setAttribute('data-dom-el', 'true');
                const actionData = { found: true, action: pattern.action, phase: 'pattern_match' };

                if (pattern.action === 'dropdown' && el.tagName === 'SELECT') {
                    for (const option of el.options) {
                        if (match(option.text)) {
                            actionData.value = option.value;
                            actionData.action = 'select';
                            break;
                        }
                    }
                } else if (pattern.action === 'dropdown') {
                    actionData.searchValue = val;
                } else if (pattern.action === 'input') {
                    actionData.value = val;
                }

                return actionData;
            }
        }
    }

    return { found: false, phase: 'pattern_match' };
}
