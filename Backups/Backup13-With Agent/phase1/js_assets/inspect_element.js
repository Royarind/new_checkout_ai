(args) => {
    const { targetIndex, selector } = args;
    let element;

    // 1. Try finding element via overlay index
    if (targetIndex !== null && targetIndex !== undefined) {
        const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
        if (overlay) {
            const rect = overlay.getBoundingClientRect();
            const centerX = rect.left + (rect.width / 2);
            const centerY = rect.top + (rect.height / 2);
            element = document.elementFromPoint(centerX, centerY);
        }
    }

    // 2. Fallback: Try finding element via selector or data attribute
    if (!element && selector) {
        element = document.querySelector(selector);
    }

    // 3. Fallback: generic data-dom-el
    if (!element) {
        element = document.querySelector('[data-dom-el]');
    }

    if (!element) return { found: false };

    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);

    // Check if obscured
    const centerX = rect.left + (rect.width / 2);
    const centerY = rect.top + (rect.height / 2);
    let isObscured = false;

    // Only check obscuration if it's within viewport
    if (rect.top >= 0 && rect.bottom <= window.innerHeight && rect.left >= 0 && rect.right <= window.innerWidth) {
        const topEl = document.elementFromPoint(centerX, centerY);
        if (topEl && !element.contains(topEl) && !topEl.contains(element) && topEl !== element) {
            // Allow if topEl is a known overlay wrapper or label
            if (topEl.tagName !== 'LABEL' && !topEl.classList.contains('overlay-wrapper')) {
                isObscured = true;
            }
        }
    }

    return {
        found: true,
        tagName: element.tagName,
        rect: {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            top: rect.top,
            bottom: rect.bottom,
            left: rect.left,
            right: rect.right
        },
        center: {
            x: centerX,
            y: centerY
        },
        window: {
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            scrollX: window.scrollX,
            scrollY: window.scrollY
        },
        isEnabled: !element.disabled && !element.classList.contains('disabled') && style.pointerEvents !== 'none',
        isVisible: (rect.top >= 0 && rect.bottom <= window.innerHeight && rect.left >= 0 && rect.right <= window.innerWidth),
        isObscured: isObscured,
        style: {
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity
        }
    };
}
