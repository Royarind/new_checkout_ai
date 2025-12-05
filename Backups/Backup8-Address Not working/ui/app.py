"""CHKout.ai - Main Dash Application"""

import dash
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import json
import asyncio
from threading import Thread
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import COLORS, APP_TITLE, APP_PORT, SCREENSHOT_INTERVAL
from components.chat_panel import create_chat_panel, format_message
from components.info_cards import create_info_cards, format_product_info, format_contact_info, format_address_info
from services.conversation_agent import ConversationAgent
from services.screenshot_service import ScreenshotService
from main_orchestrator import run_full_flow

# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.title = APP_TITLE

# Global services
conversation_agent = ConversationAgent()
screenshot_service = ScreenshotService()
automation_page = None  # Store page reference for screenshots

# Layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H2([
                html.Span("CHK", style={'color': '#00d4ff'}),
                html.Span("out.ai", style={'color': '#fff'})
            ], className='mb-0'),
            html.P("Intelligent Conversational Checkout", style={'color': '#8892b0', 'font-size': '14px', 'margin': '0'})
        ], width=8),
        dbc.Col([
            html.Div(id='status-indicator', children=[
                html.Span("● ", style={'color': '#00ff88', 'font-size': '20px'}),
                html.Span("Ready", style={'color': '#00ff88'})
            ], style={'text-align': 'right', 'padding-top': '10px'})
        ], width=4)
    ], className='mb-2', style={'padding': '10px 0', 'border-bottom': '1px solid #2a3f5f'}),
    
    # Main content
    dbc.Row([
        # Left panel - Browser view
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🌐 Live Browser", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600'}),
                dbc.CardBody([
                    html.Div(id='browser-view', children=[
                        html.Div("Browser will appear here when automation starts", 
                                style={'color': '#8892b0', 'text-align': 'center', 'padding': '100px 20px'})
                    ], style={'background-color': '#000', 'min-height': '300px', 'border-radius': '8px'})
                ], style={'background-color': '#141b2d'})
            ], style={'border': '1px solid #2a3f5f', 'margin-bottom': '10px'}),
            
            # Control buttons
            dbc.ButtonGroup([
                dbc.Button("🚀 1-Click Checkout", id='quick-buy-btn', color='primary', disabled=True, style={'font-weight': '600'}),
                dbc.Button("▶ Start Automation", id='start-btn', color='success', disabled=True, style={'font-weight': '600'}),
                dbc.Button("🔄 Start Over Fresh", id='reset-btn', color='warning', style={'font-weight': '600'})
            ], style={'width': '100%'})
        ], width=6),
        
        # Right panel - Chat and info
        dbc.Col([
            create_chat_panel(),
            create_info_cards()
        ], width=6)
    ]),
    
    # Hidden stores
    dcc.Store(id='conversation-history', data=[]),
    dcc.Store(id='json-data', data={'tasks': []}),
    dcc.Interval(id='screenshot-interval', interval=SCREENSHOT_INTERVAL, disabled=True),
    dcc.Interval(id='payment-check-interval', interval=2000, disabled=True),
    
    # Confirmation Modal
    dbc.Modal([
        dbc.ModalHeader("Confirm Purchase Details", style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody(id='confirm-modal-body', style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("✏️ Edit Details", id='edit-details-btn', color='info', style={'font-weight': '600'}),
            dbc.Button("✓ Confirm & Start", id='confirm-start-btn', color='success', style={'font-weight': '600'}),
            dbc.Button("Cancel", id='cancel-modal-btn', color='secondary')
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='confirm-modal', is_open=False, size='lg', style={'background-color': '#0a1929'})
    
], fluid=True, style={'background-color': COLORS['background'], 'min-height': '100vh', 'padding': '10px', 'max-width': '100%'})


# Clientside callback for auto-scroll
app.clientside_callback(
    """
    function(children) {
        setTimeout(function() {
            var chatContainer = document.getElementById('chat-messages');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }, 100);
        return window.dash_clientside.no_update;
    }
    """,
    Output('chat-messages', 'data-scroll'),
    Input('chat-messages', 'children')
)

# Callbacks
@app.callback(
    [Output('chat-messages', 'children'),
     Output('conversation-history', 'data'),
     Output('json-data', 'data'),
     Output('chat-input', 'value'),
     Output('product-info', 'children'),
     Output('contact-info', 'children'),
     Output('address-info', 'children'),
     Output('json-display', 'children'),
     Output('start-btn', 'disabled'),
     Output('quick-buy-btn', 'disabled')],
    [Input('send-button', 'n_clicks'),
     Input('chat-input', 'n_submit')],
    [State('chat-input', 'value'),
     State('conversation-history', 'data'),
     State('json-data', 'data')]
)
def handle_chat(n_clicks, n_submit, message, history, json_data):
    """Handle chat messages"""
    
    if not message or not message.strip():
        return dash.no_update
    
    # Add user message to history
    history.append({'role': 'user', 'content': message})
    
    # Process with conversation agent (sync wrapper for async)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(conversation_agent.process_message(message))
    loop.close()
    
    # Add AI response to history
    history.append({'role': 'assistant', 'content': response['message']})
    
    # Update JSON
    json_data = response['json_data']
    
    # Format messages
    messages = []
    for msg in history:
        is_user = msg['role'] == 'user'
        messages.append(format_message(msg['content'], is_user))
    
    # Update info cards
    product_info = format_product_info(json_data)
    contact_info = format_contact_info(json_data)
    address_info = format_address_info(json_data)
    json_display = html.Pre(json.dumps(json_data, indent=2), 
                           style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
    
    # Validate JSON completeness
    required_fields = {
        'url': bool(json_data.get('tasks', [{}])[0].get('url') if json_data.get('tasks') else False),
        'variant': bool(json_data.get('tasks', [{}])[0].get('selectedVariant') if json_data.get('tasks') else False),
        'quantity': bool(json_data.get('tasks', [{}])[0].get('quantity') if json_data.get('tasks') else False),
        'email': bool(json_data.get('customer', {}).get('contact', {}).get('email')),
        'firstName': bool(json_data.get('customer', {}).get('contact', {}).get('firstName')),
        'lastName': bool(json_data.get('customer', {}).get('contact', {}).get('lastName')),
        'address': bool(json_data.get('customer', {}).get('shippingAddress', {}).get('addressLine1')),
        'city': bool(json_data.get('customer', {}).get('shippingAddress', {}).get('city')),
        'province': bool(json_data.get('customer', {}).get('shippingAddress', {}).get('province')),
        'postal': bool(json_data.get('customer', {}).get('shippingAddress', {}).get('postalCode'))
    }
    
    missing = [k for k, v in required_fields.items() if not v]
    all_complete = len(missing) == 0
    
    # Add validation status to JSON display
    validation_status = f"✓ Complete" if all_complete else f"⚠ Missing: {', '.join(missing)}"
    json_display = html.Div([
        html.Div(validation_status, style={'color': '#00ff88' if all_complete else '#ffaa00', 'margin-bottom': '8px', 'font-weight': 'bold'}),
        html.Pre(json.dumps(json_data, indent=2), style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
    ])
    
    # Enable start button only if all data is complete
    start_disabled = not all_complete
    
    print(f"\n{'='*60}")
    print(f"UI VALIDATION: {'COMPLETE' if all_complete else 'INCOMPLETE'}")
    print(f"Missing fields: {missing if missing else 'None'}")
    print(f"Start button: {'ENABLED' if not start_disabled else 'DISABLED'}")
    print(f"{'='*60}\n")
    
    return messages, history, json_data, '', product_info, contact_info, address_info, json_display, start_disabled, start_disabled


# Initialize with welcome message
@app.callback(
    Output('chat-messages', 'children', allow_duplicate=True),
    Input('chat-messages', 'id'),
    prevent_initial_call='initial_duplicate'
)
def initialize_chat(_):
    """Show welcome message"""
    welcome = format_message(
        "Hi! I'm CHKout.ai 👋\n\nI'll help you automate your checkout process. "
        "Just share a product URL to get started!",
        is_user=False
    )
    return [welcome]


# Start automation callback
@app.callback(
    [Output('status-indicator', 'children'),
     Output('start-btn', 'disabled', allow_duplicate=True),
     Output('screenshot-interval', 'disabled'),
     Output('payment-check-interval', 'disabled', allow_duplicate=True)],
    Input('start-btn', 'n_clicks'),
    State('json-data', 'data'),
    prevent_initial_call=True
)
def start_automation(n_clicks, json_data):
    """Start the automation backend"""
    if not n_clicks:
        return dash.no_update
    
    # Validate and fix JSON data format
    import sys
    print("\n" + "="*60, flush=True)
    print("VALIDATING JSON DATA BEFORE AUTOMATION", flush=True)
    print("="*60, flush=True)
    print(json.dumps(json_data, indent=2), flush=True)
    sys.stdout.flush()
    
    # Ensure proper structure
    if 'customer' not in json_data:
        print("ERROR: Missing 'customer' key")
        return dash.no_update
    
    if 'tasks' not in json_data or not json_data['tasks']:
        print("ERROR: Missing 'tasks' key")
        return dash.no_update
    
    # Validate customer data
    customer = json_data['customer']
    if 'contact' not in customer:
        print("ERROR: Missing 'contact' in customer")
        return dash.no_update
    
    if 'shippingAddress' not in customer:
        print("ERROR: Missing 'shippingAddress' in customer")
        return dash.no_update
    
    # Ensure all required fields exist
    contact = customer['contact']
    address = customer['shippingAddress']
    task = json_data['tasks'][0]
    
    required_contact = ['email', 'firstName', 'lastName']
    required_address = ['addressLine1', 'city', 'province', 'postalCode']
    required_task = ['url', 'quantity']
    
    missing = []
    for field in required_contact:
        if not contact.get(field):
            missing.append(f"contact.{field}")
    
    for field in required_address:
        if not address.get(field):
            missing.append(f"address.{field}")
    
    for field in required_task:
        if not task.get(field):
            missing.append(f"task.{field}")
    
    if missing:
        print(f"ERROR: Missing required fields: {missing}")
        return dash.no_update
    
    # Ensure phone exists (can be empty string)
    if 'phone' not in contact:
        contact['phone'] = ''
    
    # Ensure addressLine2 exists
    if 'addressLine2' not in address:
        address['addressLine2'] = ''
    
    # Ensure country exists
    if 'country' not in address:
        address['country'] = 'US'
    
    # Ensure selectedVariant exists
    if 'selectedVariant' not in task:
        task['selectedVariant'] = {}
    
    # Ensure options and metadata exist
    if 'options' not in task:
        task['options'] = [{'name': '', 'values': []}]
    
    if 'metadata' not in task:
        task['metadata'] = {'title': '', 'description': '', 'primaryImage': '', 'price': ''}
    
    # Ensure shippingMethod exists
    if 'shippingMethod' not in customer:
        customer['shippingMethod'] = {'strategy': 'cheapest'}
    
    # Ensure payment exists
    if 'payment' not in customer:
        customer['payment'] = {
            'provider': 'nekuda',
            'data': {'userId': 'Y21GdFpYTm9jMlYwYUdsdFlXNWhkbVJvWVhKdFlVQm5iV0ZwYkM1amIyMD0='}
        }
    
    print("\n✅ JSON VALIDATION PASSED", flush=True)
    print("Final JSON to be sent:", flush=True)
    print(json.dumps(json_data, indent=2), flush=True)
    print("="*60 + "\n", flush=True)
    sys.stdout.flush()
    
    # Update status to running
    status = html.Div([
        html.Span("● ", style={'color': '#ffaa00', 'font-size': '20px'}),
        html.Span("Running...", style={'color': '#ffaa00'})
    ], style={'text-align': 'right', 'padding-top': '10px'})
    
    # Start automation in background thread
    def run_automation():
        global automation_page
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_full_flow(json_data))
        loop.close()
        print(f"\n{'='*60}")
        if result['success']:
            print("✅ Automation completed successfully!")
        else:
            print(f"❌ Automation failed: {result.get('error')}")
        print(f"{'='*60}\n")
    
    thread = Thread(target=run_automation, daemon=True)
    thread.start()
    
    return status, True, False, False  # Enable screenshot and payment check intervals


# Screenshot update callback
@app.callback(
    Output('browser-view', 'children'),
    Input('screenshot-interval', 'n_intervals')
)
def update_screenshot(n):
    """Update browser screenshot"""
    screenshot = screenshot_service.get_latest()
    if screenshot:
        return html.Img(
            src=f'data:image/png;base64,{screenshot}',
            style={'width': '100%', 'height': 'auto', 'border-radius': '8px'}
        )
    return html.Div(
        "Browser will appear here when automation starts",
        style={'color': '#8892b0', 'text-align': 'center', 'padding': '100px 20px'}
    )


# Payment ready notification callback
@app.callback(
    [Output('chat-messages', 'children', allow_duplicate=True),
     Output('payment-check-interval', 'disabled')],
    Input('payment-check-interval', 'n_intervals'),
    State('chat-messages', 'children'),
    prevent_initial_call=True
)
def check_payment_ready(n, current_messages):
    """Check if payment page is reached and notify user"""
    notification_file = '/tmp/chkout_payment_ready.txt'
    
    if os.path.exists(notification_file):
        # Delete notification file
        try:
            os.remove(notification_file)
        except:
            pass
        
        # Add payment ready message
        payment_message = format_message(
            "🎉 Great news! Your order is ready for payment!\n\n"
            "✅ Product added to cart\n"
            "✅ Shipping information filled\n"
            "✅ Payment page reached\n\n"
            "Please complete the payment in the browser to finalize your order.",
            is_user=False
        )
        
        if current_messages:
            return current_messages + [payment_message], True
        return [payment_message], True
    
    return dash.no_update, dash.no_update


# Quick Buy button - show confirmation modal
@app.callback(
    [Output('confirm-modal', 'is_open'),
     Output('confirm-modal-body', 'children')],
    [Input('quick-buy-btn', 'n_clicks'),
     Input('cancel-modal-btn', 'n_clicks'),
     Input('edit-details-btn', 'n_clicks')],
    [State('json-data', 'data'),
     State('confirm-modal', 'is_open')],
    prevent_initial_call=True
)
def toggle_confirmation_modal(quick_clicks, cancel_clicks, edit_clicks, json_data, is_open):
    """Show/hide confirmation modal with purchase details"""
    ctx = callback_context
    if not ctx.triggered:
        return False, ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'quick-buy-btn':
        # Build confirmation display
        task = json_data.get('tasks', [{}])[0]
        contact = json_data.get('customer', {}).get('contact', {})
        address = json_data.get('customer', {}).get('shippingAddress', {})
        
        # Format variants
        variants = task.get('selectedVariant', {})
        variant_str = ', '.join([f"{k}: {v}" for k, v in variants.items() if k != '__user_specified__']) if variants else 'None'
        
        confirmation_content = html.Div([
            html.H5("🛍️ Product Details", style={'color': '#00d4ff', 'margin-top': '0', 'margin-bottom': '15px'}),
            html.Div([
                html.Strong("URL: ", style={'color': '#8892b0'}),
                html.Span(task.get('url', 'N/A')[:80] + '...', style={'color': '#fff'})
            ], style={'margin-bottom': '8px'}),
            html.Div([
                html.Strong("Variant: ", style={'color': '#8892b0'}),
                html.Span(variant_str, style={'color': '#fff'})
            ], style={'margin-bottom': '8px'}),
            html.Div([
                html.Strong("Quantity: ", style={'color': '#8892b0'}),
                html.Span(str(task.get('quantity', 'N/A')), style={'color': '#fff'})
            ], style={'margin-bottom': '15px'}),
            
            html.Hr(style={'border-color': '#2a3f5f'}),
            html.H5("👤 Contact Information", style={'color': '#00d4ff', 'margin-top': '15px', 'margin-bottom': '15px'}),
            html.Div([
                html.Strong("Name: ", style={'color': '#8892b0'}),
                html.Span(f"{contact.get('firstName', '')} {contact.get('lastName', '')}", style={'color': '#fff'})
            ], style={'margin-bottom': '8px'}),
            html.Div([
                html.Strong("Email: ", style={'color': '#8892b0'}),
                html.Span(contact.get('email', 'N/A'), style={'color': '#fff'})
            ], style={'margin-bottom': '8px'}),
            html.Div([
                html.Strong("Phone: ", style={'color': '#8892b0'}),
                html.Span(contact.get('phone', 'N/A'), style={'color': '#fff'})
            ], style={'margin-bottom': '15px'}),
            
            html.Hr(style={'border-color': '#2a3f5f'}),
            html.H5("📦 Shipping Address", style={'color': '#00d4ff', 'margin-top': '15px', 'margin-bottom': '15px'}),
            html.Div([
                html.Div(address.get('addressLine1', 'N/A'), style={'color': '#fff', 'margin-bottom': '5px'}),
                html.Div(f"{address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}", style={'color': '#fff', 'margin-bottom': '5px'}),
                html.Div(address.get('country', 'US'), style={'color': '#fff'})
            ], style={'margin-bottom': '15px'}),
            
            html.Hr(style={'border-color': '#2a3f5f'}),
            html.Div("⚠️ This will start the automated checkout process immediately.", 
                    style={'color': '#ffaa00', 'font-weight': 'bold', 'margin-top': '15px', 'text-align': 'center'})
        ])
        
        return True, confirmation_content
    
    elif button_id == 'cancel-modal-btn':
        return False, ""
    
    elif button_id == 'edit-details-btn':
        return False, ""
    
    return is_open, ""


# Confirm and start automation from modal
@app.callback(
    [Output('status-indicator', 'children', allow_duplicate=True),
     Output('start-btn', 'disabled', allow_duplicate=True),
     Output('screenshot-interval', 'disabled', allow_duplicate=True),
     Output('confirm-modal', 'is_open', allow_duplicate=True),
     Output('payment-check-interval', 'disabled', allow_duplicate=True)],
    Input('confirm-start-btn', 'n_clicks'),
    State('json-data', 'data'),
    prevent_initial_call=True
)
def confirm_and_start(n_clicks, json_data):
    """Start automation after confirmation"""
    if not n_clicks:
        return dash.no_update
    
    # Update status to running
    status = html.Div([
        html.Span("● ", style={'color': '#ffaa00', 'font-size': '20px'}),
        html.Span("Running...", style={'color': '#ffaa00'})
    ], style={'text-align': 'right', 'padding-top': '10px'})
    
    # Start automation in background thread
    def run_automation():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_full_flow(json_data))
        loop.close()
        print(f"\n{'='*60}")
        if result['success']:
            print("✅ Automation completed successfully!")
        else:
            print(f"❌ Automation failed: {result.get('error')}")
        print(f"{'='*60}\n")
    
    thread = Thread(target=run_automation, daemon=True)
    thread.start()
    
    return status, True, False, False, False  # Close modal and enable payment check


# Reset/Start Over Fresh button
@app.callback(
    [Output('conversation-history', 'data', allow_duplicate=True),
     Output('json-data', 'data', allow_duplicate=True),
     Output('chat-messages', 'children', allow_duplicate=True),
     Output('browser-view', 'children', allow_duplicate=True)],
    Input('reset-btn', 'n_clicks'),
    prevent_initial_call=True
)
def reset_conversation(n_clicks):
    """Reset conversation and delete saved profile"""
    if not n_clicks:
        return dash.no_update
    
    # Delete saved profile
    import os
    profile_file = os.path.expanduser('~/.chkout_profile.json')
    if os.path.exists(profile_file):
        os.remove(profile_file)
        print("Saved profile deleted")
    
    # Delete screenshot to clear browser view
    screenshot_path = '/tmp/chkout_screenshot.png'
    if os.path.exists(screenshot_path):
        os.remove(screenshot_path)
        print("Screenshot deleted")
    
    # Reset conversation agent
    conversation_agent.reset()
    
    # Show welcome message
    welcome = format_message(
        "Hi! I'm CHKout.ai 👋\n\nI'll help you automate your checkout process. "
        "Just share a product URL to get started!",
        is_user=False
    )
    
    # Clear browser view
    browser_placeholder = html.Div(
        "Browser will appear here when automation starts",
        style={'color': '#8892b0', 'text-align': 'center', 'padding': '100px 20px'}
    )
    
    return [], {'tasks': []}, [welcome], browser_placeholder


if __name__ == '__main__':
    import sys
    print(f"\n{'='*60}")
    print(f"🚀 CHKout.ai Starting...")
    print(f"{'='*60}")
    print(f"📱 Open: http://localhost:{APP_PORT}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    app.run(debug=True, port=APP_PORT)
