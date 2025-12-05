/**
 * Advanced DOM Element Extractor for E-commerce Automation
 * Extracts and indexes interactive elements for product variant selection
 */

class DOMExtractor {
    constructor() {
        this.relevantKeywords = [
            'size', 'color', 'variant', 'option', 'select', 'add', 'cart', 
            'bag', 'buy', 'purchase', 'quantity', 'fit', 'style', 'checkout',
            'small', 'medium', 'large', 'xl', 'xxl', 'red', 'blue', 'black', 
            'white', 'green', 'yellow', 'pink', 'grey', 'gray'
        ];
        
        this.interactiveTags = [
            'button', 'input', 'select', 'a', 'div', 'span', 'label', 'li', 'option'
        ];
    }

    /**
     * Check if element is relevant for product selection
     */
    isRelevantElement(element) {
        const text = (element.textContent || '').toLowerCase();
        const className = (element.className || '').toLowerCase();
        const id = (element.id || '').toLowerCase();
        const dataAttrs = this.getDataAttributes(element).toLowerCase();
        const ariaLabel = (element.getAttribute('aria-label') || '').toLowerCase();
        
        const searchText = `${text} ${className} ${id} ${dataAttrs} ${ariaLabel}`;
        
        return this.relevantKeywords.some(keyword => searchText.includes(keyword)) ||
               this.hasInteractiveAttributes(element) ||
               this.isProductVariantElement(element);
    }

    /**
     * Get all data attributes as string
     */
    getDataAttributes(element) {
        return Array.from(element.attributes)
            .filter(attr => attr.name.startsWith('data-'))
            .map(attr => `${attr.name}=${attr.value}`)
            .join(' ');
    }

    /**
     * Check if element has interactive attributes
     */
    hasInteractiveAttributes(element) {
        const interactiveAttrs = ['onclick', 'onchange', 'role', 'tabindex'];
        return interactiveAttrs.some(attr => element.hasAttribute(attr));
    }

    /**
     * Check if element is likely a product variant selector
     */
    isProductVariantElement(element) {
        const parent = element.parentElement;
        if (!parent) return false;
        
        const parentClass = (parent.className || '').toLowerCase();
        const parentId = (parent.id || '').toLowerCase();
        
        const variantIndicators = [
            'variant', 'option', 'selector', 'picker', 'choice', 'selection'
        ];
        
        return variantIndicators.some(indicator => 
            parentClass.includes(indicator) || parentId.includes(indicator)
        );
    }

    /**
     * Generate unique CSS selector for element
     */
    generateSelector(element) {
        // Try ID first
        if (element.id) {
            return `#${element.id}`;
        }
        
        // Try unique class combination
        if (element.className) {
            const classes = element.className.split(' ')
                .filter(c => c.trim())
                .join('.');
            if (classes) {
                const selector = `${element.tagName.toLowerCase()}.${classes}`;
                if (document.querySelectorAll(selector).length === 1) {
                    return selector;
                }
            }
        }
        
        // Generate path-based selector
        return this.generatePathSelector(element);
    }

    /**
     * Generate path-based CSS selector
     */
    generatePathSelector(element) {
        const path = [];
        let current = element;
        
        while (current && current !== document.body) {
            let selector = current.tagName.toLowerCase();
            
            if (current.id) {
                selector += `#${current.id}`;
                path.unshift(selector);
                break;
            }
            
            if (current.className) {
                const classes = current.className.split(' ')
                    .filter(c => c.trim())
                    .slice(0, 2) // Limit to first 2 classes
                    .join('.');
                if (classes) {
                    selector += `.${classes}`;
                }
            }
            
            // Add nth-child if needed for uniqueness
            const siblings = Array.from(current.parentElement?.children || [])
                .filter(sibling => sibling.tagName === current.tagName);
            if (siblings.length > 1) {
                const index = siblings.indexOf(current) + 1;
                selector += `:nth-child(${index})`;
            }
            
            path.unshift(selector);
            current = current.parentElement;
        }
        
        return path.join(' > ');
    }

    /**
     * Get element visibility and position info
     */
    getElementInfo(element) {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        
        return {
            visible: rect.width > 0 && rect.height > 0 && style.display !== 'none',
            position: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            },
            clickable: this.isClickable(element),
            interactable: this.isInteractable(element)
        };
    }

    /**
     * Check if element is clickable
     */
    isClickable(element) {
        const style = window.getComputedStyle(element);
        return style.pointerEvents !== 'none' && 
               !element.disabled &&
               (element.tagName === 'BUTTON' || 
                element.tagName === 'A' || 
                element.onclick ||
                style.cursor === 'pointer');
    }

    /**
     * Check if element is interactable
     */
    isInteractable(element) {
        return element.tagName === 'INPUT' || 
               element.tagName === 'SELECT' || 
               element.tagName === 'TEXTAREA' ||
               this.isClickable(element);
    }

    /**
     * Extract all relevant DOM elements
     */
    extractElements() {
        const elements = [];
        let index = 0;

        this.interactiveTags.forEach(tag => {
            const tagElements = document.querySelectorAll(tag);
            
            tagElements.forEach(element => {
                if (this.isRelevantElement(element)) {
                    const elementInfo = this.getElementInfo(element);
                    
                    elements.push({
                        index: index++,
                        tag: element.tagName.toLowerCase(),
                        text: (element.textContent || '').trim().substring(0, 150),
                        value: element.value || '',
                        attributes: this.getElementAttributes(element),
                        selector: this.generateSelector(element),
                        ...elementInfo,
                        type: element.type || '',
                        name: element.name || '',
                        role: element.getAttribute('role') || '',
                        ariaLabel: element.getAttribute('aria-label') || ''
                    });
                }
            });
        });

        return elements.filter(el => el.visible); // Only return visible elements
    }

    /**
     * Get element attributes as object
     */
    getElementAttributes(element) {
        const attrs = {};
        Array.from(element.attributes).forEach(attr => {
            attrs[attr.name] = attr.value;
        });
        return attrs;
    }

    /**
     * Find elements by variant type
     */
    findVariantElements(variantType, variantValue) {
        const elements = this.extractElements();
        const lowerValue = (variantValue || '').toLowerCase();
        
        return elements.filter(element => {
            const searchText = `${element.text} ${element.value} ${JSON.stringify(element.attributes)}`.toLowerCase();
            
            switch (variantType) {
                case 'color':
                    return this.isColorElement(element, lowerValue);
                case 'size':
                    return this.isSizeElement(element, lowerValue);
                case 'quantity':
                    return this.isQuantityElement(element);
                case 'cart':
                    return this.isCartElement(element);
                default:
                    return searchText.includes(lowerValue);
            }
        });
    }

    /**
     * Check if element is color-related
     */
    isColorElement(element, colorValue) {
        const colorKeywords = ['color', 'colour', 'swatch'];
        const searchText = `${element.text} ${JSON.stringify(element.attributes)}`.toLowerCase();
        
        return colorKeywords.some(keyword => searchText.includes(keyword)) &&
               (searchText.includes(colorValue) || element.text.toLowerCase().includes(colorValue));
    }

    /**
     * Check if element is size-related
     */
    isSizeElement(element, sizeValue) {
        const sizeKeywords = ['size', 'fit'];
        const searchText = `${element.text} ${JSON.stringify(element.attributes)}`.toLowerCase();
        
        return sizeKeywords.some(keyword => searchText.includes(keyword)) &&
               (searchText.includes(sizeValue) || element.text.toLowerCase().includes(sizeValue));
    }

    /**
     * Check if element is quantity-related
     */
    isQuantityElement(element) {
        const quantityKeywords = ['quantity', 'qty', 'amount'];
        const searchText = `${element.text} ${JSON.stringify(element.attributes)}`.toLowerCase();
        
        return quantityKeywords.some(keyword => searchText.includes(keyword)) ||
               (element.tag === 'input' && element.type === 'number');
    }

    /**
     * Check if element is cart-related
     */
    isCartElement(element) {
        const cartKeywords = ['add to cart', 'add to bag', 'buy now', 'purchase', 'checkout'];
        const searchText = element.text.toLowerCase();
        
        return cartKeywords.some(keyword => searchText.includes(keyword));
    }
}

// Export for use in Playwright
(() => {
    const extractor = new DOMExtractor();
    return extractor.extractElements();
});