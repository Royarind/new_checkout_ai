(args) => {
    const { variantType, variantValue } = args;

    // Strict normalization (removes spaces)
    const normalizeStrict = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';

    // Fuzzy normalization (keeps spaces, useful for multi-word matches)
    const normalizeFuzzy = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ') : '';

    const normalizedTargetStrict = normalizeStrict(variantValue);
    const normalizedTargetFuzzy = normalizeFuzzy(variantValue);

    console.log('🔍 VERIFICATION: Checking if', variantType, '=', variantValue, 'is actually selected');
    console.log('🔍 Normalized target (strict):', normalizedTargetStrict);
    console.log('🔍 Normalized target (fuzzy):', normalizedTargetFuzzy);

    // Helper to check if text matches (tries both strict and fuzzy)
    const matches = (text) => {
        if (!text) return false;
        const textStrict = normalizeStrict(text);
        const textFuzzy = normalizeFuzzy(text);

        // Exact match (strict)
        if (textStrict === normalizedTargetStrict) return true;

        // Fuzzy match (keeps spaces)
        if (textFuzzy === normalizedTargetFuzzy) return true;

        // Contains match (for longer text containing the variant)
        if (textStrict.includes(normalizedTargetStrict) || textFuzzy.includes(normalizedTargetFuzzy)) return true;

        return false;
    };

    // Check 1: URL parameters (for sites that put variant in URL)
    const url = window.location.href;
    if (matches(url)) {
        console.log('✅ VERIFIED via URL:', variantValue);
        return { verified: true, method: 'URL', actualValue: variantValue };
    }

    // Check 2: Checked radio buttons
    const radios = document.querySelectorAll('input[type="radio"]:checked');
    for (const radio of radios) {
        // Check radio value
        if (matches(radio.value)) {
            console.log('✅ VERIFIED via radio value:', radio.value);
            return { verified: true, method: 'radio_value', actualValue: radio.value };
        }

        // Check label
        const label = document.querySelector(`label[for="${radio.id}"]`);
        if (label && matches(label.textContent)) {
            console.log('✅ VERIFIED via radio label:', label.textContent.trim());
            return { verified: true, method: 'radio_label', actualValue: label.textContent.trim() };
        }

        // Check aria-label
        const ariaLabel = radio.getAttribute('aria-label');
        if (ariaLabel && matches(ariaLabel)) {
            console.log('✅ VERIFIED via aria-label:', ariaLabel);
            return { verified: true, method: 'aria_label', actualValue: ariaLabel };
        }

        // Check data attributes
        const dataColor = radio.getAttribute('data-color') || radio.getAttribute('data-value');
        if (dataColor && matches(dataColor)) {
            console.log('✅ VERIFIED via data attribute:', dataColor);
            return { verified: true, method: 'data_attribute', actualValue: dataColor };
        }
    }

    // Check 3: Selected state elements (buttons, divs, etc.)
    const selectedSelectors = [
        '.selected',
        '.active',
        '[aria-selected="true"]',
        '[aria-pressed="true"]',
        '[aria-checked="true"]',
        '[aria-current="true"]',
        '[data-selected="true"]',
        '.is-selected',
        '.is-active',
        'button[aria-pressed="true"]',
        'button.selected',
        'button.active',
        '[class*="selected"]',
        '[class*="active"]',
        '[class*="checked"]'
    ];

    for (const selector of selectedSelectors) {
        const selectedElements = document.querySelectorAll(selector);
        for (const el of selectedElements) {
            // FILTER: For colors, only check elements in color-related containers
            if (variantType === 'color') {
                const colorContainer = el.closest('[class*="color"], [class*="swatch"], [data-color], section');
                if (!colorContainer) continue;

                // Skip size/navigation elements
                const ctx = (el.className + ' ' + el.id).toLowerCase();
                if (ctx.includes('size') || ctx.includes('nav') || ctx.includes('menu')) continue;
            }

            // Check text content
            if (matches(el.textContent)) {
                console.log('✅ VERIFIED via selected element text:', el.textContent.trim(), '(selector:', selector + ')');
                return { verified: true, method: 'selected_element', actualValue: el.textContent.trim() };
            }

            // Check aria-label
            const ariaLabel = el.getAttribute('aria-label');
            if (ariaLabel && matches(ariaLabel)) {
                console.log('✅ VERIFIED via selected element aria-label:', ariaLabel, '(selector:', selector + ')');
                return { verified: true, method: 'selected_aria_label', actualValue: ariaLabel };
            }

            // Check title
            const title = el.getAttribute('title');
            if (title && matches(title)) {
                console.log('✅ VERIFIED via selected element title:', title, '(selector:', selector + ')');
                return { verified: true, method: 'selected_title', actualValue: title };
            }

            // Check data attributes (common for color swatches)
            const dataAttrs = ['data-name', 'data-color', 'data-value', 'data-shade', 'data-variant'];
            for (const attr of dataAttrs) {
                const value = el.getAttribute(attr);
                if (value && matches(value)) {
                    console.log('✅ VERIFIED via', attr + ':', value, '(selector:', selector + ')');
                    return { verified: true, method: attr, actualValue: value };
                }
            }
        }
    }

    // Check 4: Currently displayed selection (common pattern: "Selected: Cool Brown" or similar)
    const displayElements = document.querySelectorAll('[class*="current"], [class*="chosen"], [class*="display"]');
    for (const el of displayElements) {
        if (matches(el.textContent)) {
            console.log('✅ VERIFIED via display element:', el.textContent.trim());
            return { verified: true, method: 'display_element', actualValue: el.textContent.trim() };
        }
    }

    // VERIFICATION FAILED - Collect diagnostic information
    const actuallySelected = [];

    // Check all radios
    const allRadios = document.querySelectorAll('input[type="radio"]:checked');
    allRadios.forEach(radio => {
        const label = document.querySelector(`label[for="${radio.id}"]`);
        if (label) actuallySelected.push({ type: 'radio', value: label.textContent.trim() });
        else if (radio.value) actuallySelected.push({ type: 'radio', value: radio.value });
        else if (radio.getAttribute('aria-label')) actuallySelected.push({ type: 'radio', value: radio.getAttribute('aria-label') });
    });

    // Check all selected elements
    const allSelected = document.querySelectorAll('.selected, .active, [aria-selected="true"], [aria-pressed="true"], [aria-checked="true"], [aria-current="true"]');
    allSelected.forEach(el => {
        const text = el.textContent?.trim();
        const ariaLabel = el.getAttribute('aria-label');
        const title = el.getAttribute('title');
        const dataColor = el.getAttribute('data-color') || el.getAttribute('data-name');

        if (text && text.length < 100) actuallySelected.push({ type: 'selected', value: text });
        if (ariaLabel) actuallySelected.push({ type: 'aria-label', value: ariaLabel });
        if (title) actuallySelected.push({ type: 'title', value: title });
        if (dataColor) actuallySelected.push({ type: 'data-attr', value: dataColor });
    });

    console.log('❌ VERIFICATION FAILED');
    console.log('Expected:', variantValue);
    console.log('Found selected elements:', actuallySelected);
    return { verified: false, expected: variantValue, actuallySelected: actuallySelected };
}
