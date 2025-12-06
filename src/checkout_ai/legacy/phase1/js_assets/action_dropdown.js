(targetIndex) => {
    const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
    if (overlay) {
        const rect = overlay.getBoundingClientRect();
        const centerX = rect.left + (rect.width / 2);
        const centerY = rect.top + (rect.height / 2);
        const el = document.elementFromPoint(centerX, centerY);
        if (el) {
            const elementRect = el.getBoundingClientRect();
            const isInViewport = elementRect.top >= 0 && elementRect.left >= 0 &&
                elementRect.bottom <= window.innerHeight &&
                elementRect.right <= window.innerWidth;
            if (!isInViewport) {
                el.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }
        }
    }
}

// Helper to click dropdown
async function clickDropdown(targetIndex) {
    const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
    if (!overlay) return { success: false, reason: 'No overlay found' };

    const rect = overlay.getBoundingClientRect();
    const centerX = rect.left + (rect.width / 2);
    const centerY = rect.top + (rect.height / 2);
    const targetEl = document.elementFromPoint(centerX, centerY);
    if (!targetEl) return { success: false, reason: 'No target element' };

    // Strategy 1: Direct click on target
    try {
        targetEl.scrollIntoView({ block: 'center' });
        if (typeof targetEl.click === 'function') {
            targetEl.click();
            return { success: true, strategy: 'direct' };
        }
    } catch (e) {
        console.log('Direct click failed:', e);
    }

    // Strategy 2: Find Vue Select dropdown toggle
    const vueSelect = targetEl.closest('.v-select') || document.querySelector('.v-select');
    if (vueSelect) {
        const toggle = vueSelect.querySelector('.vs__dropdown-toggle');
        if (toggle) {
            try {
                toggle.scrollIntoView({ block: 'center' });
                if (typeof toggle.click === 'function') {
                    toggle.click();
                    return { success: true, strategy: 'vue-toggle' };
                }
            } catch (e) {
                console.log('Vue toggle click failed:', e);
            }
        }
    }

    // Strategy 3: Parent traversal with clickability check
    let currentEl = targetEl;
    let attempts = 0;
    const maxAttempts = 5;

    while (currentEl && attempts < maxAttempts) {
        try {
            // Check if element is clickable
            const rect = currentEl.getBoundingClientRect();
            const style = window.getComputedStyle(currentEl);

            const isClickable = rect.width > 0 && rect.height > 0 &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                style.pointerEvents !== 'none';

            if (isClickable) {
                currentEl.scrollIntoView({ block: 'center' });
                if (typeof currentEl.click === 'function') {
                    currentEl.click();
                    return { success: true, strategy: 'traversal', element: currentEl.tagName + '.' + currentEl.className };
                }
            }
        } catch (e) {
            console.log(`Click failed on ${currentEl.tagName}, trying parent:`, e);
        }

        // Move to parent element
        currentEl = currentEl.parentElement;
        attempts++;
    }

    return { success: false, reason: 'All strategies failed including parent traversal' };
}

// Helper to select option
function selectOption(val) {
    const normalize = (text) => text ? text.toLowerCase().trim() : '';
    const match = (text) => normalize(text).includes(normalize(val));

    const selectors = [
        '[role="option"]', 'option', 'li',
        '[class*="option"]', '[class*="item"]',
        '[class*="choice"]', '[class*="select"]',
        '.vs__dropdown-option', '[class*="vs__option"]'
    ];

    for (const sel of selectors) {
        for (const opt of document.querySelectorAll(sel)) {
            if (match(opt.textContent)) {
                opt.scrollIntoView({ block: 'center' });
                opt.click();
                return true;
            }
        }
    }
    return false;
}
