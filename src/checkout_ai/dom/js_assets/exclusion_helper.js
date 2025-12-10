/**
 * Helper function to check if an element is inside an excluded section
 * (e.g., recommendations, related products, similar items)
 * 
 * This prevents selecting variant elements from "You may also like" or 
 * "Similar Products" sections which can have the same variant names.
 */
function isInExcludedSection(element) {
    if (!element) return true;

    // Excluded section patterns (recommendations, related products, etc.)
    const EXCLUDED_SELECTORS = [
        // Generic patterns
        '[class*="recommend"]',
        '[class*="similar"]',
        '[class*="related"]',
        '[class*="you-may"]',
        '[class*="also-like"]',
        '[class*="also-bought"]',
        '[class*="customers-bought"]',
        '[class*="recently-viewed"]',
        '[class*="recently-bought"]',
        '[class*="popular"]',
        '[class*="trending"]',
        '[id*="recommend"]',
        '[id*="similar"]',
        '[id*="carousel"]',
        '[id*="related"]',
        '[data-widget*="recommendation"]',
        '[data-widget*="similar"]',
        '[data-component*="recommendation"]',

        // Common class names
        '.recommendations',
        '.similar-products',
        '.related-products',
        '.product-recommendations',
        '.carousel',
        '.slider',

        // Indian site-specific
        '.similiar-products',  // Myntra typo
        '.recommended-products',
        '.you-may-also-like',
        '.customers-who-bought',
        '.frequently-bought-together'
    ];

    // Check if element or any parent matches excluded selectors
    for (const selector of EXCLUDED_SELECTORS) {
        try {
            if (element.closest(selector)) {
                return true;
            }
        } catch (e) {
            // Invalid selector, skip
            continue;
        }
    }

    return false;
}
