(args) => {
    const { variantType, variantValue } = args;
    const normalize = (text) => text ? text.toLowerCase().trim().replace(/[^a-z0-9]/g, '') : '';
    const normalizedTarget = normalize(variantValue);

    console.log('🔍 DISCOVERY: Looking for', variantType, '=', variantValue);
    console.log('🔍 Normalized target:', normalizedTarget);

    // Discover all clickable elements that might be variant options
    const potentialElements = [];

    // Strategy 1: Find radio buttons (common for colors/sizes)
    const radios = document.querySelectorAll('input[type="radio"]');
    console.log('📻 Found', radios.length, 'radio buttons');

    radios.forEach((radio, index) => {
        const label = document.querySelector(`label[for="${radio.id}"]`);
        const labelText = label ? label.textContent?.trim() : '';
        const value = radio.value;
        const ariaLabel = radio.getAttribute('aria-label');

        // Get all possible texts
        const texts = [value, labelText, ariaLabel].filter(t => t);

        potentialElements.push({
            index: index,
            element: radio,
            type: 'radio',
            texts: texts,
            normalizedTexts: texts.map(t => normalize(t)),
            id: radio.id,
            name: radio.name
        });
    });

    // Strategy 2: Find buttons/links that might be variant selectors
    const buttons = document.querySelectorAll('button, a, [role="button"]');
    console.log('🔘 Found', buttons.length, 'buttons/links');

    buttons.forEach((btn, index) => {
        const text = btn.textContent?.trim();
        const ariaLabel = btn.getAttribute('aria-label');
        const title = btn.getAttribute('title');
        const dataValue = btn.getAttribute('data-value');

        // Priority: text content > aria-label > title > data-value (data-value can be ID)
        // Only include SHORT texts that are likely user-visible labels (not long descriptions or IDs)
        const texts = [];

        // Prioritize actual displayed text
        if (text && text.length < 30 && text.length > 0) {
            texts.push({ value: text, priority: 1, source: 'textContent' });
        }

        if (ariaLabel && ariaLabel.length < 30) {
            texts.push({ value: ariaLabel, priority: 2, source: 'aria-label' });
        }

        if (title && title.length < 30) {
            texts.push({ value: title, priority: 3, source: 'title' });
        }

        // Only include data-value if it's short and looks like a label (not an ID)
        // IDs typically are long numbers or alphanumeric strings like "60264341"
        if (dataValue && dataValue.length < 15 && !/^\d{5,}$/.test(dataValue)) {
            texts.push({ value: dataValue, priority: 4, source: 'data-value' });
        }

        if (texts.length > 0) {
            potentialElements.push({
                index: index,
                element: btn,
                type: 'button',
                texts: texts.map(t => t.value),
                textPriorities: texts.map(t => t.priority),
                textSources: texts.map(t => t.source),
                normalizedTexts: texts.map(t => normalize(t.value)),
                className: btn.className
            });
        }
    });

    console.log('📦 Total potential elements:', potentialElements.length);

    // Try to match with our target value
    let bestMatch = null;
    let bestMatchScore = 0;
    let bestTextIndex = -1;

    for (const item of potentialElements) {
        for (let i = 0; i < item.normalizedTexts.length; i++) {
            const normalized = item.normalizedTexts[i];
            const priority = item.textPriorities ? item.textPriorities[i] : 5;

            // Exact match - prioritize by text source priority
            if (normalized === normalizedTarget) {
                const score = 100 - priority; // Lower priority number = higher score
                if (score > bestMatchScore) {
                    const source = item.textSources ? item.textSources[i] : 'unknown';
                    console.log('✅ EXACT MATCH:', item.texts[i], '(source:', source, ', priority:', priority, ')');
                    bestMatch = item;
                    bestMatchScore = score;
                    bestTextIndex = i;
                }
            }

            // Partial match (contains) - but with lower score
            else if ((normalized.includes(normalizedTarget) || normalizedTarget.includes(normalized)) && normalized.length < 20) {
                const score = 50 - priority;
                if (score > bestMatchScore) {
                    const source = item.textSources ? item.textSources[i] : 'unknown';
                    console.log('🎯 PARTIAL MATCH:', item.texts[i], '(source:', source, ')');
                    bestMatch = item;
                    bestMatchScore = score;
                    bestTextIndex = i;
                }
            }
        }
    }

    if (!bestMatch) {
        console.log('❌ No matches found in discovery phase');
        return { found: false, allOptions: potentialElements.slice(0, 20).map(e => e.texts) };
    }

    // Log what we matched
    console.log('🎯 Best match found:', bestMatch.texts[bestTextIndex], '(score:', bestMatchScore, ')');

    // Try to click the matched element
    console.log('🎯 Attempting to click best match...');
    const element = bestMatch.element;

    // Mark for later reference
    element.setAttribute('data-discovery-matched', 'true');

    // Scroll into view
    element.scrollIntoView({ block: 'center', behavior: 'smooth' });

    // Try click strategies
    let clicked = false;

    // Strategy 1: Direct click
    try {
        element.click();
        clicked = true;
        console.log('✅ Direct click succeeded');
    } catch (e) {
        console.log('❌ Direct click failed:', e.message);
    }

    // Strategy 2: For radio buttons, set checked and dispatch change
    if (!clicked && bestMatch.type === 'radio') {
        try {
            element.checked = true;
            element.dispatchEvent(new Event('change', { bubbles: true }));
            clicked = element.checked;
            console.log('✅ Radio click succeeded');
        } catch (e) {
            console.log('❌ Radio click failed:', e.message);
        }
    }

    // Strategy 3: Mouse events (last resort)
    if (!clicked) {
        try {
            const rect = element.getBoundingClientRect();
            const events = ['mousedown', 'mouseup', 'click'];
            events.forEach(eventType => {
                element.dispatchEvent(new MouseEvent(eventType, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: rect.left + rect.width / 2,
                    clientY: rect.top + rect.height / 2
                }));
            });
            clicked = true;
            console.log('✅ Mouse events dispatched');
        } catch (e) {
            console.log('❌ Mouse events failed:', e.message);
        }
    }

    return {
        found: true,
        clicked: clicked,
        matchedText: bestMatch.texts[0],
        matchScore: bestMatchScore,
        elementType: bestMatch.type
    };
}
