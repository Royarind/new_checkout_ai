#!/usr/bin/env python3
"""
Interactive Dash Chat System for Checkout AI
Natural language → JSON → Automated checkout with live progress
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from agent.llm_client import LLMClient
import os

load_dotenv()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Global state
checkout_state = {
    'running': False,
    'progress': [],
    'payload': None,
    'pending_prompt': None,
    'prompt_response': None
}

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H2("🛒 Checkout AI - Interactive Chat", className="text-center mt-4 mb-4"),
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div(id='chat-history', style={
                        'height': '400px',
                        'overflowY': 'scroll',
                        'border': '1px solid #ddd',
                        'padding': '10px',
                        'marginBottom': '10px',
                        'backgroundColor': '#f8f9fa'
                    }),
                    dbc.InputGroup([
                        dbc.Input(id='user-input', placeholder='Enter your checkout request...', type='text'),
                        dbc.Button('Send', id='send-btn', color='primary'),
                    ]),
                    html.Div([
                        dbc.Button('🔄 Reset', id='reset-btn', color='warning', className='mt-2 me-2'),
                        dbc.Button('▶️ Start Checkout', id='start-btn', color='success', className='mt-2', disabled=True),
                    ]),
                    dbc.Modal([
                        dbc.ModalHeader(dbc.ModalTitle(id='prompt-title')),
                        dbc.ModalBody([
                            html.P(id='prompt-message'),
                            dbc.Input(id='prompt-input', type='password', placeholder='Enter password...')
                        ]),
                        dbc.ModalFooter([
                            dbc.Button('Submit', id='prompt-submit', color='primary'),
                            dbc.Button('Cancel', id='prompt-cancel', color='secondary')
                        ])
                    ], id='prompt-modal', is_open=False)
                ])
            ])
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Live Progress"),
                dbc.CardBody([
                    html.Div(id='progress-log', style={
                        'height': '450px',
                        'overflowY': 'scroll',
                        'fontFamily': 'monospace',
                        'fontSize': '12px',
                        'backgroundColor': '#1e1e1e',
                        'color': '#00ff00',
                        'padding': '10px'
                    })
                ])
            ])
        ], width=6)
    ]),
    
    dcc.Store(id='conversation-store', data={'messages': [], 'payload': None}),
    dcc.Interval(id='progress-interval', interval=500, disabled=True),
    dcc.Interval(id='prompt-check-interval', interval=500, disabled=False)
], fluid=True)


async def convert_to_json(user_message, conversation_history, current_payload):
    """Convert natural language to checkout JSON using LLM"""
    llm = LLMClient(provider='groq', model='llama-3.3-70b-versatile')
    
    # Initialize payload structure if empty
    if not current_payload:
        current_payload = {
            'customer': {'contact': {}, 'shippingAddress': {}, 'shippingMethod': {'strategy': 'cheapest'}},
            'tasks': [{'quantity': 1, 'selectedVariant': {}}]
        }
    
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in conversation_history[-5:]])
    
    prompt = f"""Extract checkout information from user message and build JSON incrementally.

CURRENT DATA:
{json.dumps(current_payload, indent=2) if current_payload else 'None'}

CONVERSATION:
{history_text}

USER: {user_message}

EXTRACT from user message:
- Product URL (if mentioned)
- Product details (color, size, quantity)
- Customer name, email, phone
- Shipping address (street, city, state, zip, country)

RULES:
1. Extract ONLY what user provided in current message
2. Merge with CURRENT DATA - keep existing fields, add new ones
3. NEVER ask for fields already in CURRENT DATA
4. Ask for ONE missing field at a time (prioritize: URL → variants → contact → address)
5. When ALL required fields present, return status="complete"

REQUIRED FIELDS:
- tasks[0].url
- tasks[0].selectedVariant (color, size)
- customer.contact (email, firstName, lastName, phone)
- customer.shippingAddress (addressLine1, city, province, postalCode, country)

RETURN JSON:
{{"status": "complete"|"incomplete", "payload": {{customer: {{contact: {{email, firstName, lastName, phone}}, shippingAddress: {{addressLine1, city, province, postalCode, country}}}}, tasks: [{{url, quantity, selectedVariant: {{color, size}}}}]}}, "question": "What is your email?"}}

JSON:"""
    
    response = await llm.complete(prompt, max_tokens=1000)
    return response


@app.callback(
    [Output('chat-history', 'children'),
     Output('conversation-store', 'data'),
     Output('start-btn', 'disabled'),
     Output('user-input', 'value')],
    [Input('send-btn', 'n_clicks'),
     Input('reset-btn', 'n_clicks')],
    [State('user-input', 'value'),
     State('conversation-store', 'data')]
)
def handle_chat(send_clicks, reset_clicks, user_input, store_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return [], {'messages': [], 'payload': None}, True, ''
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'reset-btn':
        checkout_state['progress'] = []
        checkout_state['payload'] = None
        return [], {'messages': [], 'payload': None}, True, ''
    
    if button_id == 'send-btn' and user_input:
        messages = store_data.get('messages', [])
        messages.append({'role': 'user', 'content': user_input, 'time': datetime.now().strftime('%H:%M:%S')})
        
        # Convert to JSON with current payload
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(convert_to_json(user_input, messages, store_data.get('payload')))
        loop.close()
        
        # Always update payload with new data
        if response.get('payload'):
            store_data['payload'] = response.get('payload')
        
        if response.get('status') == 'complete':
            messages.append({'role': 'assistant', 'content': '✅ All information collected! Click "Start Checkout" to begin.', 'time': datetime.now().strftime('%H:%M:%S')})
            checkout_state['payload'] = response.get('payload')
            start_disabled = False
        else:
            question = response.get('question', 'Please provide more information.')
            # Show what we collected so far
            collected = []
            payload = store_data.get('payload', {})
            if payload.get('tasks'):
                collected.append(f"✅ Product: {payload['tasks'][0].get('url', 'N/A')[:50]}...")
                if payload['tasks'][0].get('selectedVariant'):
                    collected.append(f"✅ Variant: {payload['tasks'][0]['selectedVariant']}")
            if payload.get('customer', {}).get('contact', {}).get('email'):
                collected.append(f"✅ Email: {payload['customer']['contact']['email']}")
            
            summary = '\n'.join(collected) if collected else ''
            full_msg = f"{summary}\n\n{question}" if summary else question
            messages.append({'role': 'assistant', 'content': full_msg, 'time': datetime.now().strftime('%H:%M:%S')})
            start_disabled = True
        
        store_data['messages'] = messages
        
        # Render chat
        chat_elements = []
        for msg in messages:
            if msg['role'] == 'user':
                chat_elements.append(html.Div([
                    html.Small(msg['time'], className='text-muted'),
                    html.Div(msg['content'], className='p-2 mb-2 bg-primary text-white rounded')
                ], style={'textAlign': 'right'}))
            else:
                chat_elements.append(html.Div([
                    html.Small(msg['time'], className='text-muted'),
                    html.Div(msg['content'], className='p-2 mb-2 bg-light rounded')
                ]))
        
        return chat_elements, store_data, start_disabled, ''
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


@app.callback(
    Output('progress-interval', 'disabled'),
    Input('start-btn', 'n_clicks'),
    prevent_initial_call=True
)
def start_checkout(n_clicks):
    if n_clicks and checkout_state['payload']:
        checkout_state['running'] = True
        checkout_state['progress'] = ['🚀 Starting checkout process...']
        
        # Run checkout in background thread
        import threading
        thread = threading.Thread(target=run_checkout_background)
        thread.start()
        
        return False
    return True


def run_checkout_background():
    """Run checkout in background and update progress"""
    import asyncio
    from app_reactive import run_reactive_checkout
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # User prompt callback for password
    async def user_prompt_callback(field_type, message):
        checkout_state['pending_prompt'] = {'type': field_type, 'message': message}
        checkout_state['prompt_response'] = None
        checkout_state['progress'].append(f"⏸️ Waiting for user input: {field_type}")
        
        # Wait for user response (max 60 seconds)
        for _ in range(120):
            await asyncio.sleep(0.5)
            if checkout_state['prompt_response'] is not None:
                response = checkout_state['prompt_response']
                checkout_state['pending_prompt'] = None
                checkout_state['prompt_response'] = None
                return response
        
        checkout_state['pending_prompt'] = None
        return None
    
    try:
        loop.run_until_complete(run_reactive_checkout(checkout_state['payload'], user_prompt_callback))
        checkout_state['progress'].append('✅ Checkout completed!')
    except Exception as e:
        checkout_state['progress'].append(f'❌ Error: {str(e)}')
    finally:
        checkout_state['running'] = False
        loop.close()


@app.callback(
    Output('progress-log', 'children'),
    Input('progress-interval', 'n_intervals')
)
def update_progress(n):
    if checkout_state['progress']:
        return [html.Div(line) for line in checkout_state['progress']]
    return html.Div('Waiting to start...', style={'color': '#888'})


if __name__ == '__main__':
    print("🚀 Starting Dash Chat App on http://localhost:8050")
    app.run(debug=True, port=8050)


@app.callback(
    [Output('prompt-modal', 'is_open'),
     Output('prompt-title', 'children'),
     Output('prompt-message', 'children'),
     Output('prompt-input', 'value')],
    [Input('prompt-check-interval', 'n_intervals'),
     Input('prompt-submit', 'n_clicks'),
     Input('prompt-cancel', 'n_clicks')],
    [State('prompt-input', 'value')]
)
def handle_prompt(n_intervals, submit_clicks, cancel_clicks, input_value):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, '', '', ''
    
    trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger == 'prompt-submit' and input_value:
        checkout_state['prompt_response'] = input_value
        return False, '', '', ''
    
    if trigger == 'prompt-cancel':
        checkout_state['prompt_response'] = ''
        return False, '', '', ''
    
    if trigger == 'prompt-check-interval' and checkout_state.get('pending_prompt'):
        prompt = checkout_state['pending_prompt']
        return True, f"Input Required: {prompt['type'].title()}", prompt['message'], ''
    
    return False, '', '', ''
