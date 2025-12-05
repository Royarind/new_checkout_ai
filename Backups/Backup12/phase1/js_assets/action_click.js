(targetIndex) => {
    let element;

    // 1. Try finding element via overlay index (Overlay Search)
    if (targetIndex !== null && targetIndex !== undefined) {
        const overlay = document.querySelector(`[data-element-index="${targetIndex}"]`);
        if (overlay) {
            const rect = overlay.getBoundingClientRect();
            const centerX = rect.left + (rect.width / 2);
            const centerY = rect.top + (rect.height / 2);
            element = document.elementFromPoint(centerX, centerY);
        }
    }

    // 2. Fallback: Try finding element via data-dom-el attribute (Pattern Match / DOM Tree)
    if (!element) {
        element = document.querySelector('[data-dom-el]');
    }

    if (!element) return false;

    // Check if element is in viewport, scroll if needed
    const elementRect = element.getBoundingClientRect();
    const isInViewport = elementRect.top >= 0 && elementRect.left >= 0 &&
        elementRect.bottom <= window.innerHeight &&
        elementRect.right <= window.innerWidth;

    if (!isInViewport) {
        console.log('Element not in viewport, initiating slow smooth scroll...');

        // Calculate target position (center element in viewport)
        const targetY = window.scrollY + elementRect.top - (window.innerHeight / 2) + (elementRect.height / 2);
        const startY = window.scrollY;
        const distance = targetY - startY;
        const duration = 1000; // 1 second duration
        let startTime = null;

        // Easing function (Quadratic Ease In/Out)
        const ease = (t, b, c, d) => {
            t /= d / 2;
            if (t < 1) return c / 2 * t * t + b;
            t--;
            return -c / 2 * (t * (t - 2) - 1) + b;
        };

        // Animation loop
        const animation = (currentTime) => {
            if (startTime === null) startTime = currentTime;
            const timeElapsed = currentTime - startTime;
            const run = ease(timeElapsed, startY, distance, duration);
            window.scrollTo(0, run);
            if (timeElapsed < duration) {
                requestAnimationFrame(animation);
            }
        };

        requestAnimationFrame(animation);

        // Wait for scroll animation to complete + buffer
        return new Promise(resolve => setTimeout(() => {
            console.log('Scroll complete, clicking element');
            element.click();
            resolve(true);
        }, duration + 200));
    }

    // Multiple click strategies
    const strategies = [
        // Strategy A0: WooCommerce variation items (li with data-value)
        () => {
            if (element.tagName === 'LI' && element.getAttribute('data-value') &&
                (element.classList.contains('variable-item') || element.classList.contains('color-variable-item'))) {
                console.log('WooCommerce variation item detected');
                element.scrollIntoView({ block: 'center' });
                element.click();
                // Also update hidden select if present
                const hiddenSelect = element.closest('.woo-variation-items-wrapper')?.querySelector('select[style*="display:none"], select.woo-variation-raw-select');
                if (hiddenSelect) {
                    const dataValue = element.getAttribute('data-value');
                    hiddenSelect.value = dataValue;
                    hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    console.log('Updated hidden select to:', dataValue);
                }
                return true;
            }
            return false;
        },

        // Strategy A: Direct click (with type check)
        () => {
            if (typeof element.click === 'function') {
                element.click();
                return true;
            }
            return false;
        },

        // Strategy B: Focus then click
        () => {
            if (element.focus) element.focus();
            if (typeof element.click === 'function') {
                element.click();
                return true;
            }
            return false;
        },

        // Strategy C: Enhanced mouse events for images
        () => {
            const rect = element.getBoundingClientRect();
            const centerX = rect.left + (rect.width / 2);
            const centerY = rect.top + (rect.height / 2);

            // For images, try clicking at the center coordinates
            if (element.tagName === 'IMG') {
                const clickableParent = document.elementFromPoint(centerX, centerY);
                if (clickableParent && clickableParent !== element && typeof clickableParent.click === 'function') {
                    clickableParent.click();
                    return true;
                }
            }

            const events = ['mousedown', 'mouseup', 'click'];
            events.forEach(eventType => {
                const event = new MouseEvent(eventType, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: centerX,
                    clientY: centerY
                });
                element.dispatchEvent(event);
            });
            return true;
        },

        // Strategy D: For radio/checkbox inputs
        () => {
            if (element.type === 'radio' || element.type === 'checkbox') {
                element.checked = true;
                element.dispatchEvent(new Event('change', { bubbles: true }));
                return element.checked;
            }
            return false;
        },

        // Strategy E: Enhanced container and input finding
        () => {
            // For images, look for clickable containers with data attributes
            if (element.tagName === 'IMG') {
                let container = element.parentElement;
                let depth = 0;
                while (container && depth < 5) {
                    // Check for Saks-style selectable containers
                    if (container.getAttribute('data-testid')?.includes('selectable') ||
                        container.classList && container.classList.contains('selectable') ||
                        container.classList && container.classList.contains('clickable') ||
                        container.getAttribute('role') === 'button') {

                        if (typeof container.click === 'function') {
                            container.click();
                            return true;
                        }

                        // Try mouse events on container
                        const rect = container.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            const centerX = rect.left + (rect.width / 2);
                            const centerY = rect.top + (rect.height / 2);
                            const event = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: centerX,
                                clientY: centerY
                            });
                            container.dispatchEvent(event);
                            return true;
                        }
                    }
                    container = container.parentElement;
                    depth++;
                }
            }

            // Look for radio/checkbox in container
            const container = element.closest('.sitg-input-inner-wrapper') ||
                element.closest('[data-testid="sitg-input-inner-wrapper"]') ||
                element.parentElement;

            if (container) {
                const input = container.querySelector('input[type="radio"], input[type="checkbox"]');
                if (input) {
                    input.checked = true;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    return input.checked;
                }
            }

            // Look for label association (PRIORITY)
            if (element.tagName === 'LABEL') {
                // 1. Check 'for' attribute
                if (element.getAttribute('for')) {
                    const input = document.getElementById(element.getAttribute('for'));
                    if (input) {
                        // Try clicking the input directly
                        if (typeof input.click === 'function') {
                            input.click();
                            return true;
                        }
                        // Or setting checked
                        if (input.type === 'radio' || input.type === 'checkbox') {
                            input.checked = true;
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('click', { bubbles: true }));
                            return input.checked;
                        }
                    }
                }

                // 2. Check if input is nested inside label
                const nestedInput = element.querySelector('input');
                if (nestedInput) {
                    if (typeof nestedInput.click === 'function') {
                        nestedInput.click();
                        return true;
                    }
                    if (nestedInput.type === 'radio' || nestedInput.type === 'checkbox') {
                        nestedInput.checked = true;
                        nestedInput.dispatchEvent(new Event('change', { bubbles: true }));
                        nestedInput.dispatchEvent(new Event('click', { bubbles: true }));
                        return nestedInput.checked;
                    }
                }
            }

            return false;
        },

        // Strategy F: Enhanced parent traversal click
        () => {
            let parent = element.parentElement;
            let depth = 0;
            while (parent && depth < 8) {  // Increased depth for complex sites
                try {
                    // Check if parent is clickable
                    const style = window.getComputedStyle(parent);
                    const isClickable = parent.onclick ||
                        parent.getAttribute('onclick') ||
                        style.cursor === 'pointer' ||
                        parent.classList && parent.classList.contains('clickable') ||
                        parent.classList && parent.classList.contains('selectable') ||
                        parent.hasAttribute('role');

                    if (isClickable && typeof parent.click === 'function') {
                        parent.click();
                        return true;
                    }

                    // For images, also try mouse events on parent
                    if (element.tagName === 'IMG' && parent.tagName !== 'BODY') {
                        const rect = parent.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            const centerX = rect.left + (rect.width / 2);
                            const centerY = rect.top + (rect.height / 2);
                            const event = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: centerX,
                                clientY: centerY
                            });
                            parent.dispatchEvent(event);
                            return true;
                        }
                    }
                } catch (e) {
                    // Continue to next parent
                }
                parent = parent.parentElement;
                depth++;
            }
            return false;
        }
    ];

    // Try each strategy
    for (let i = 0; i < strategies.length; i++) {
        try {
            if (strategies[i]()) {
                console.log(`Click strategy ${String.fromCharCode(65 + i)} succeeded`);
                return true;
            }
        } catch (e) {
            console.log(`Click strategy ${String.fromCharCode(65 + i)} failed:`, e);
        }
    }

    return false;
}
