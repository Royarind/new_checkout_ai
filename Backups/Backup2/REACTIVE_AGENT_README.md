# Reactive Agent System

## Overview

New reactive agent architecture that implements **observe-reason-act loop** similar to the example you provided.

## Architecture

### Old System (Batch Planning):
```
LLM → [action1, action2, action3] → Execute all → Done
```

### New System (Reactive):
```
Loop:
  1. Observe page state
  2. LLM reasons and decides next action
  3. Execute ONE action
  4. Observe result
  5. Repeat until goal achieved
```

## Key Features

1. **Iterative Reasoning**: LLM sees result of each action before deciding next
2. **Course Correction**: Can adapt strategy if action fails
3. **Text-Based Observation**: No vision needed - sends buttons, inputs, errors to LLM
4. **Rule-Based Tools**: Can call existing rule-based functions as tools
5. **Conversation History**: Maintains context of previous actions

## Files

- `agent/reactive_agent.py` - Main reactive agent with observe-reason-act loop
- `agent/reactive_agent_factory.py` - Factory to create agent
- `app_reactive.py` - Demo app using reactive agent

## Usage

```bash
python3 app_reactive.py
```

Then paste your JSON payload.

## How It Works

### 1. Observation
Agent extracts from page:
- URL and title
- All visible buttons (text, aria-label, class)
- All visible input fields (name, placeholder, label)
- Error messages
- Body text snippet

### 2. Reasoning
LLM receives:
- Current observation
- Goal
- Customer data
- Previous 5 actions and results
- Available tools

LLM responds with:
- Reasoning (what it sees and why)
- Next action to take
- Confidence level
- Whether goal is achieved

### 3. Action
Agent executes ONE action:
- `click_button(text)` - Click button
- `fill_field(name, value)` - Fill input
- `select_dropdown(name, value)` - Select dropdown
- `press_key(key)` - Press keyboard key
- `wait(seconds)` - Wait
- `scroll(direction)` - Scroll page
- `use_rule_based(action)` - Call existing rule-based function

### 4. Loop
Repeats until:
- Goal achieved (LLM says so)
- Max iterations reached (20)
- Error occurs

## Example Flow

```
Iteration 1:
  Observe: See "Add to Cart" modal with "Checkout" button
  Reason: "I see checkout button in modal, I should click it"
  Act: click_button("Checkout")
  Result: Success, page navigated

Iteration 2:
  Observe: See email field, first name field, last name field
  Reason: "I see contact form, I should fill email first"
  Act: fill_field("email", "john@example.com")
  Result: Success, email filled

Iteration 3:
  Observe: Email filled, name fields still empty
  Reason: "Email filled successfully, now fill first name"
  Act: fill_field("first name", "John")
  Result: Success, first name filled

... continues until checkout complete
```

## Advantages Over Old System

1. **Adaptive**: Can change strategy mid-execution
2. **Observant**: Sees result of each action
3. **Resilient**: Can recover from failures
4. **Transparent**: Clear reasoning at each step
5. **Flexible**: Not locked into initial plan

## Old Agent System

The old `planner_agent.py`, `executor_agent.py`, and `agent_coordinator.py` are **kept for reference** but not used by reactive agent. They can be deleted if reactive agent works well.

## Testing

Start with simple goal:
```
Goal: "Click the checkout button and fill email field with test@example.com"
```

Then expand to full checkout.

## Limitations

- Max 20 iterations (configurable)
- No vision (text-based only)
- Depends on LLM quality
- May be slower than rule-based (more LLM calls)

## Future Improvements

- Add vision support (screenshots)
- Smarter tool selection
- Better error recovery
- Parallel action execution
- Learning from past runs
