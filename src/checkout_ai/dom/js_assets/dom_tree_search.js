(args) => {
    const { variantValue, containerSelector } = args;
    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
    const target = normalize(variantValue);

    // Helper to check visibility
    const isVisible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0' &&
            rect.width > 0 &&
            rect.height > 0;
    };

    // Helper to score verification
    const getScore = (el, text) => {
        const normText = normalize(text);
        if (normText === target) return 100;
        if (normText.includes(target)) return 80; // "32 inch" includes "32"
        if (target.includes(normText)) return 60;
        return 0;
    };

    const container = containerSelector ? document.querySelector(containerSelector) : document.body;
    if (!container) return { found: false };

    // Selectors for common variant elements (buttons, list items, divs with text)
    // Added specific classes for Flipkart/Amazon/Myntra
    const candidates = Array.from(container.querySelectorAll('button, li, div, ul > li, a, span, [role="button"], [class*="swatch"], [class*="variant"]'));

    let bestMatch = null;
    let bestScore = 0;

    for (const el of candidates) {
        if (!isVisible(el)) continue;

        // Get all text sources
        const texts = [
            el.textContent,
            el.getAttribute('aria-label'),
            el.getAttribute('title'),
            el.getAttribute('value'),
            el.getAttribute('data-value')
        ];

        // Specific handling for Flipkart/Myntra tiles (often have nested info)
        // If element has few children, it might be a button text wrapper
        if (el.children.length < 3) {
            // check inner text
        }

        for (const t of texts) {
            if (!t) continue;
            const score = getScore(el, t);

            // Boost score if element looks interactive
            const isInteractive = el.tagName === 'BUTTON' ||
                el.tagName === 'A' ||
                el.getAttribute('role') === 'button' ||
                el.className.includes('selected') ||
                el.className.includes('active');

            const finalScore = score + (isInteractive ? 10 : 0);

            if (finalScore > bestScore && finalScore > 50) { // Threshold
                bestScore = finalScore;
                bestMatch = el;
            }
        }
    }

    if (bestMatch) {
        // Generate unique selector or index
        // We'll use a data attribute to mark it for the python side to click
        const uniqueId = 'v_' + Math.random().toString(36).substr(2, 9);
        bestMatch.setAttribute('data-dom-el', uniqueId);

        return {
            found: true,
            action: 'click',
            value: uniqueId, // Return ID for selector
            text: bestMatch.textContent,
            score: bestScore
        };
    }

    return { found: false };
}
