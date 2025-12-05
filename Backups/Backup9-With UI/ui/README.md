# CHKout.ai - Intelligent Conversational Checkout System

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd ui
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Open Browser
Navigate to: `http://localhost:8050`

---

## 💬 How to Use

### Step 1: Start Conversation
- Type a product URL in the chat
- CHKout.ai will analyze the page and detect required variants

### Step 2: Provide Product Details
- Answer questions about size, color, quantity
- The AI will only ask for variants that exist on the product page

### Step 3: Provide Contact Information
- Email (required for checkout)
- Name (required)
- Phone (optional - say "skip" if you don't want to provide)

### Step 4: Provide Shipping Address
- Street address, city, state, ZIP
- Or say "no" to enter manually in the browser

### Step 5: Start Automation
- Click "▶ Start" button when ready
- Watch the live browser view on the left
- CHKout.ai will automate the entire checkout process

---

## 🎨 Features

✅ **Intelligent Conversation** - Natural language interaction  
✅ **Automatic Variant Detection** - Detects size/color options from product page  
✅ **Progressive JSON Building** - Builds checkout data as you chat  
✅ **Graceful Stopping** - Stops when you skip required information  
✅ **Live Browser View** - See automation in real-time  
✅ **Dark Professional Theme** - Easy on the eyes  
✅ **Password Support** - Handles login scenarios securely  

---

## 📁 Project Structure

```
ui/
├── app.py                      # Main Dash application
├── config.py                   # Configuration
├── assets/
│   └── style.css              # Dark theme CSS
├── components/
│   ├── chat_panel.py          # Chat interface
│   └── info_cards.py          # Information display cards
└── services/
    ├── conversation_agent.py  # LLM conversation logic
    ├── variant_detector.py    # Automatic variant detection
    └── screenshot_service.py  # Browser screenshot capture
```

---

## 🔧 Configuration

Edit `config.py` to customize:
- Colors (dark theme palette)
- Screenshot interval
- App port
- Debug mode

---

## 🤖 Conversation Examples

### Example 1: Complete Flow
```
You: https://nike.com/shirt-abc
AI: Analyzing product... I found this requires:
    • Size: XS, S, M, L, XL
    • Color: Black, White, Blue
    What size?
You: Medium
AI: What color?
You: Blue
AI: How many? (default: 1)
You: 2
AI: Perfect! Now I need your email.
You: john@email.com
AI: First name?
You: John
AI: Last name?
You: Doe
AI: Phone? (say 'skip' if you want)
You: skip
AI: No problem! Now I need your shipping address.
You: 123 Main St
AI: City?
You: Dallas
AI: State?
You: Texas
AI: ZIP code?
You: 75001
AI: Perfect! Click 'Start' to begin automation.
```

### Example 2: User Skips Address
```
You: I don't want to share my address
AI: Understood! I've completed:
    ✓ Product selection
    ✓ Contact information
    
    Click 'Start' and I'll automate up to the shipping page.
    You can enter your address manually there.
```

---

## 🛠️ Troubleshooting

### Chat not responding?
- Check that Groq API key is set in `.env`
- Check console for errors

### Browser view not showing?
- Automation must be started first
- Check that Playwright is installed

### Variants not detected?
- Some sites may have complex variant selectors
- You can manually provide variant info in chat

---

## 🎯 Next Steps

1. **Add Payment Support** - Extend to handle payment information
2. **Multi-Product Support** - Add multiple products to cart
3. **Save Profiles** - Save customer information for reuse
4. **Export JSON** - Download generated JSON for later use

---

**Built with ❤️ using Dash, Playwright, and LLM**
