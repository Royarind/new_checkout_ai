(args) => {
    const variantValue = typeof args === 'object' && args !== null ? args.variantValue : args;
    const containerSelector = typeof args === 'object' && args !== null ? args.containerSelector : null;

    const normalize = (text) => text ? String(text).toLowerCase().trim().replace(/[^a-z0-9\s]/g, '') : '';
    const normalizedVal = normalize(variantValue);

    // Helper to check visibility
    const isVisible = (node) => {
        if (!node || node.nodeType !== 1) return false;
        const style = window.getComputedStyle(node);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = node.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        return true;
    };

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

    // DOM tree search function
    const searchDOMTree = (node, depth = 0) => {
        if (!node || depth > 10) return null;
        if (node.nodeType === 1 && !isVisible(node)) return null;

        if (node.nodeType === 1) {
            const text = node.textContent?.trim();
            const value = node.value;
            const ariaLabel = node.getAttribute('aria-label');
            const title = node.getAttribute('title');
            const dataValue = node.getAttribute('data-value');

            // Skip non-product elements
            const skipPatterns = ['country', 'localization', 'currency', 'language', 'region', 'shipping', 'search', 'filter', 'sort', 'breadcrumb', 'navigation'];
            const elementInfo = (node.id + ' ' + node.className + ' ' + (node.name || '')).toLowerCase();
            const shouldSkip = skipPatterns.some(pattern => elementInfo.includes(pattern));

            // CRITICAL: Skip navigation/header elements
            let isInNavigation = false;
            let checkParent = node;
            let depth = 0;
            while (checkParent && depth < 10) {
                const tag = checkParent.tagName?.toLowerCase();
                const role = checkParent.getAttribute('role');
                const className = String(checkParent.className || '').toLowerCase();

                if (tag === 'nav' || tag === 'header' ||
                    role === 'navigation' ||
                    className.includes('navigation') ||
                    className.includes('header') ||
                    className.includes('menu')) {
                    isInNavigation = true;
                    break;
                }
                checkParent = checkParent.parentElement;
                depth++;
            }

            if (!shouldSkip && !isInNavigation) {
                if (match(text) || match(value) || match(ariaLabel) || match(title) || match(dataValue)) {
                    // CRITICAL: For links, require them to be in product area (y > 150)
                    const rect = node.getBoundingClientRect();
                    const isLink = node.tagName === 'A';

                    if (isLink && rect.top < 150) {
                        // Skip links in header area (top 150px)
                        return null;
                    }

                    const isInteractive = node.tagName === 'BUTTON' ||
                        (node.tagName === 'A' && rect.top >= 150) ||  // Only links below header
                        node.tagName === 'INPUT' ||
                        node.tagName === 'SELECT' ||
                        node.onclick ||
                        node.getAttribute('onclick') ||
                        node.style.cursor === 'pointer' ||
                        node.classList && node.classList.contains('clickable') ||
                        node.classList && node.classList.contains('selectable') ||
                        node.hasAttribute('role');

                    if (isInteractive) {
                        return node;
                    }

                    // Check parent elements
                    let parent = node.parentElement;
                    let parentDepth = 0;
                    while (parent && parentDepth < 3) {
                        const parentInteractive = parent.tagName === 'BUTTON' ||
                            parent.tagName === 'A' ||
                            parent.onclick ||
                            parent.getAttribute('onclick') ||
                            parent.style.cursor === 'pointer' ||
                            parent.classList && parent.classList.contains('clickable') ||
                            parent.classList && parent.classList.contains('selectable');

                        if (parentInteractive) {
                            return parent;
                        }
                        parent = parent.parentElement;
                        parentDepth++;
                    }
                }
            }
        }

        // Search children
        const children = node.children || node.childNodes;
        for (const child of children) {
            const found = searchDOMTree(child, depth + 1);
            if (found) return found;
        }

        // Search Shadow DOM
        if (node.shadowRoot) {
            const found = searchDOMTree(node.shadowRoot, depth + 1);
            if (found) return found;
        }

        return null;
    };

    // Search in product-focused containers
    const productContainers = [
        'form[data-product-id]',
        '.variant-selector',
        '.shade-selector',
        '[class*="product"]',
        '[class*="variant"]',
        '[class*="option"]',
        '[class*="shade"]',
        'main',
        'body'
    ];

    for (const containerSelector of productContainers) {
        const container = document.querySelector(containerSelector);
        if (container) {
            if (container.id === 'localization_form' || container.classList && container.classList.contains('localization')) {
                continue;
            }

            const found = searchDOMTree(container);
            if (found) {
                if (found.id === 'LocalizationForm-Select' ||
                    found.classList && found.classList.contains('country-picker') ||
                    found.name === 'country_code') {
                    continue;
                }

                found.setAttribute('data-dom-el', 'true');

                let action = 'click';
                if (found.tagName === 'SELECT') {
                    action = 'select';
                    for (const option of found.options) {
                        if (match(option.text)) {
                            return { found: true, action: 'select', value: option.value, phase: 'dom_tree' };
                        }
                    }
                } else if (found.classList && found.classList.contains('dropdown') || found.classList && found.classList.contains('select') || found.hasAttribute('role') && found.getAttribute('role').includes('combobox')) {
                    action = 'dropdown';
                } else if (found.tagName === 'INPUT' && found.type === 'number') {
                    action = 'quantity_input';
                }

                return { found: true, action: action, searchValue: variantValue, phase: 'dom_tree' };
            }
        }
    }

    return { found: false, phase: 'dom_tree' };
}
