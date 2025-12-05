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
from components.llm_settings import create_llm_settings_modal, create_llm_settings_button
from services.conversation_agent import ConversationAgent
from services.screenshot_service import ScreenshotService
from main_orchestrator import run_full_flow

# Import LLM config API to register callbacks
import ui.api.llm_config_api

# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    use_async=True
)
app.title = APP_TITLE

# Global services
conversation_agent = ConversationAgent()
screenshot_service = ScreenshotService()
automation_page = None  # Store page reference for screenshots

def get_conversation_agent():
    """Get the global conversation agent instance"""
    return conversation_agent

# Add custom CSS for dropdown styling
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .Select-control { color: #00d4ff !important; }
            .Select-value-label { color: #ff0000 !important; }
            .Select-menu-outer { background-color: #141b2d !important; }
            .Select-option { color: #00d4ff !important; background-color: #141b2d !important; }
            .Select-option.is-selected { color: #ff0000 !important; }
            .Select-option.is-focused { background-color: #1e2a3a !important; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

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
            html.Div([
                dbc.Button(
                    "🛒 New Checkout",
                    id='new-checkout-btn',
                    color="info",
                    outline=True,
                    size="sm",
                    className="me-2"
                ),
                create_llm_settings_button(),
                html.Div(id='status-indicator', children=[
                    html.Span("● ", style={'color': '#00ff88', 'font-size': '20px'}),
                    html.Span("Ready", style={'color': '#00ff88'})
                ], style={'display': 'inline-block'})
            ], style={'text-align': 'right', 'padding-top': '10px'})
        ], width=4)
    ], className='mb-2', style={'padding': '10px 0', 'border-bottom': '1px solid #2a3f5f'}),
    
    # Main content
    dbc.Row([
        # Left panel - Browser view
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Live Browser", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600'}),
                dbc.CardBody([
                    html.Div(id='browser-view', children=[
                        html.Div("Browser will appear here when automation starts", 
                                style={'color': '#8892b0', 'text-align': 'center', 'padding': '80px 20px'})
                    ], style={'background-color': '#000', 'height': '350px', 'border-radius': '8px', 'overflow': 'hidden'})
                ], style={'background-color': '#141b2d'})
            ], style={'border': '1px solid #2a3f5f', 'margin-bottom': '10px'}),
            
            # Control buttons
            dbc.ButtonGroup([
                dbc.Button("Edit Details", id='quick-buy-btn', color='primary', disabled=True, style={'font-weight': '600'}),
                dbc.Button("Quick Checkout", id='start-btn', color='success', disabled=True, style={'font-weight': '600'}),
                dbc.Button("Start Over", id='reset-btn', color='warning', style={'font-weight': '600'})
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
    
    # LLM Settings Modal
    create_llm_settings_modal(),
    
    # Confirmation Modal
    dbc.Modal([
        dbc.ModalHeader("Confirm Purchase Details", style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody(id='confirm-modal-body', style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("Edit Details", id='edit-details-btn', color='info', style={'font-weight': '600'}),
            dbc.Button("✓ Confirm & Start", id='confirm-start-btn', color='success', style={'font-weight': '600'}),
            dbc.Button("Cancel", id='cancel-modal-btn', color='secondary')
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='confirm-modal', is_open=False, size='lg', style={'background-color': '#0a1929'}),
    
    # Edit Details Modal
    dbc.Modal([
        dbc.ModalHeader("Edit Details", style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody([
            html.H6("Product Details", style={'color': '#00d4ff', 'margin-bottom': '10px'}),
            dbc.Input(id='edit-quantity', placeholder='Quantity', type='number', className='mb-2'),
            dbc.Input(id='edit-variant-color', placeholder='Color (optional)', className='mb-2'),
            dbc.Input(id='edit-variant-size', placeholder='Size (optional)', className='mb-3'),
            
            html.H6("Contact Information", style={'color': '#00d4ff', 'margin-bottom': '10px'}),
            dbc.Input(id='edit-email', placeholder='Email', className='mb-2'),
            dbc.Input(id='edit-password', placeholder='Password (optional - for sites requiring login)', type='password', className='mb-2'),
            dbc.Input(id='edit-firstName', placeholder='First Name', className='mb-2'),
            dbc.Input(id='edit-lastName', placeholder='Last Name', className='mb-2'),
            dbc.Input(id='edit-phone', placeholder='Phone', className='mb-3'),
            
            html.H6("Shipping Address", style={'color': '#00d4ff', 'margin-bottom': '10px'}),
            dbc.Input(id='edit-address', placeholder='Address Line 1', className='mb-2'),
            dbc.Input(id='edit-city', placeholder='City', className='mb-2'),
            dbc.Input(id='edit-province', placeholder='State/Province', className='mb-2'),
            dbc.Input(id='edit-postal', placeholder='Postal Code', className='mb-2'),
        ], style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("Cancel", id='edit-cancel-btn', color='secondary'),
            dbc.Button("Save Changes", id='edit-save-btn', color='success', style={'font-weight': '600'})
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='edit-modal', is_open=False, size='lg', style={'background-color': '#0a1929'})
    
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
async def handle_chat(n_clicks, n_submit, message, history, json_data):
    """Handle chat messages"""
    
    if not message or not message.strip():
        return dash.no_update
    
    # Add user message to history
    history.append({'role': 'user', 'content': message})
    
    # Process with conversation agent
    response = await conversation_agent.process_message(message)
    
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
        "Hi! I'm CHKout.ai!! \n\nI'll help you automate your checkout process. "
        "Just share the product URL to get started!...You can copy the URL and paste it here!\n\n",
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
    
    print("\nJSON VALIDATION PASSED", flush=True)
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
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_full_flow(json_data))
        loop.close()
        print(f"\n{'='*60}")
        if result['success']:
            print("Automation completed successfully!")
        else:
            print(f"Automation failed: {result.get('error')}")
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
            "✅ SUCCESS! All automation steps completed!\n\n"
            "✅ Product added to cart\n"
            "✅ Variants selected\n"
            "✅ Shipping information filled\n"
            "✅ Payment page reached\n\n"
            "🎉 Your order is ready! Please complete the payment in the browser to finalize your purchase.",
            is_user=False
        )
        
        if current_messages:
            return current_messages + [payment_message], True
        return [payment_message], True
    
    return dash.no_update, dash.no_update


# Edit modal callbacks
@app.callback(
    [Output('edit-modal', 'is_open'),
     Output('edit-quantity', 'value'),
     Output('edit-variant-color', 'value'),
     Output('edit-variant-size', 'value'),
     Output('edit-email', 'value'),
     Output('edit-password', 'value'),
     Output('edit-firstName', 'value'),
     Output('edit-lastName', 'value'),
     Output('edit-phone', 'value'),
     Output('edit-address', 'value'),
     Output('edit-city', 'value'),
     Output('edit-province', 'value'),
     Output('edit-postal', 'value'),
     Output('confirm-modal', 'is_open', allow_duplicate=True)],
    [Input('edit-details-btn', 'n_clicks'),
     Input('edit-cancel-btn', 'n_clicks')],
    [State('json-data', 'data'),
     State('edit-modal', 'is_open')],
    prevent_initial_call=True
)
def toggle_edit_modal(edit_clicks, cancel_clicks, json_data, is_open):
    """Open/close edit modal and populate fields"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'edit-details-btn':
        task = json_data.get('tasks', [{}])[0]
        contact = json_data.get('customer', {}).get('contact', {})
        address = json_data.get('customer', {}).get('shippingAddress', {})
        variants = task.get('selectedVariant', {})
        
        return (True, 
                task.get('quantity', 1),
                variants.get('color', ''),
                variants.get('size', ''),
                contact.get('email', ''),
                contact.get('password', ''),
                contact.get('firstName', ''),
                contact.get('lastName', ''),
                contact.get('phone', ''),
                address.get('addressLine1', ''),
                address.get('city', ''),
                address.get('province', ''),
                address.get('postalCode', ''),
                False)  # Close confirmation modal
    
    elif button_id == 'edit-cancel-btn':
        return (False,) + (dash.no_update,) * 12
    
    return dash.no_update


@app.callback(
    [Output('json-data', 'data', allow_duplicate=True),
     Output('edit-modal', 'is_open', allow_duplicate=True),
     Output('confirm-modal', 'is_open', allow_duplicate=True),
     Output('product-info', 'children', allow_duplicate=True),
     Output('contact-info', 'children', allow_duplicate=True),
     Output('address-info', 'children', allow_duplicate=True),
     Output('json-display', 'children', allow_duplicate=True),
     Output('confirm-modal-body', 'children', allow_duplicate=True)],
    Input('edit-save-btn', 'n_clicks'),
    [State('edit-quantity', 'value'),
     State('edit-variant-color', 'value'),
     State('edit-variant-size', 'value'),
     State('edit-email', 'value'),
     State('edit-password', 'value'),
     State('edit-firstName', 'value'),
     State('edit-lastName', 'value'),
     State('edit-phone', 'value'),
     State('edit-address', 'value'),
     State('edit-city', 'value'),
     State('edit-province', 'value'),
     State('edit-postal', 'value'),
     State('json-data', 'data')],
    prevent_initial_call=True
)
def save_edited_details(n_clicks, quantity, color, size, email, password, firstName, lastName, phone, address, city, province, postal, json_data):
    """Save edited details to JSON"""
    if not n_clicks:
        return dash.no_update
    
    # Update JSON with edited values
    if 'customer' not in json_data:
        json_data['customer'] = {}
    
    if 'tasks' not in json_data or not json_data['tasks']:
        json_data['tasks'] = [{}]
    
    # Update task
    json_data['tasks'][0]['quantity'] = quantity if quantity else 1
    
    # Update variants
    variants = {}
    if color:
        variants['color'] = color
    if size:
        variants['size'] = size
    json_data['tasks'][0]['selectedVariant'] = variants
    
    # Update contact
    json_data['customer']['contact'] = {
        'email': email,
        'password': password if password else '',
        'firstName': firstName,
        'lastName': lastName,
        'phone': phone
    }
    
    # Update address
    json_data['customer']['shippingAddress'] = {
        'addressLine1': address,
        'city': city,
        'province': province,
        'postalCode': postal,
        'country': json_data.get('customer', {}).get('shippingAddress', {}).get('country', 'US')
    }
    
    print("Details updated:", json.dumps(json_data, indent=2))
    
    # Update info cards
    product_info = format_product_info(json_data)
    contact_info = format_contact_info(json_data)
    address_info = format_address_info(json_data)
    json_display = html.Pre(json.dumps(json_data, indent=2), 
                           style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
    
    # Update confirmation modal body
    task = json_data.get('tasks', [{}])[0]
    contact = json_data.get('customer', {}).get('contact', {})
    address = json_data.get('customer', {}).get('shippingAddress', {})
    variants = task.get('selectedVariant', {})
    variant_str = ', '.join([f"{k}: {v}" for k, v in variants.items() if k != '__user_specified__']) if variants else 'None'
    
    confirmation_content = html.Div([
        html.H5("Product Details", style={'color': '#00d4ff', 'margin-top': '0', 'margin-bottom': '15px'}),
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
        html.H5("Contact Information", style={'color': '#00d4ff', 'margin-top': '15px', 'margin-bottom': '15px'}),
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
        html.H5("Shipping Address", style={'color': '#00d4ff', 'margin-top': '15px', 'margin-bottom': '15px'}),
        html.Div([
            html.Div(address.get('addressLine1', 'N/A'), style={'color': '#fff', 'margin-bottom': '5px'}),
            html.Div(f"{address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}", style={'color': '#fff', 'margin-bottom': '5px'}),
            html.Div(address.get('country', 'US'), style={'color': '#fff'})
        ], style={'margin-bottom': '15px'}),
        
        html.Hr(style={'border-color': '#2a3f5f'}),
        html.Div("This will start the automated checkout process immediately.", 
                style={'color': '#ffaa00', 'font-weight': 'bold', 'margin-top': '15px', 'text-align': 'center'})
    ])
    
    # Close edit modal and reopen confirmation modal
    return json_data, False, True, product_info, contact_info, address_info, json_display, confirmation_content


# Quick Buy button - show confirmation modal
@app.callback(
    [Output('confirm-modal', 'is_open'),
     Output('confirm-modal-body', 'children')],
    [Input('quick-buy-btn', 'n_clicks'),
     Input('cancel-modal-btn', 'n_clicks')],
    [State('json-data', 'data'),
     State('confirm-modal', 'is_open')],
    prevent_initial_call=True
)
def toggle_confirmation_modal(quick_clicks, cancel_clicks, json_data, is_open):
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
            html.H5("Product Details", style={'color': '#00d4ff', 'margin-top': '0', 'margin-bottom': '15px'}),
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
            html.H5("Shipping Address", style={'color': '#00d4ff', 'margin-top': '15px', 'margin-bottom': '15px'}),
            html.Div([
                html.Div(address.get('addressLine1', 'N/A'), style={'color': '#fff', 'margin-bottom': '5px'}),
                html.Div(f"{address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}", style={'color': '#fff', 'margin-bottom': '5px'}),
                html.Div(address.get('country', 'US'), style={'color': '#fff'})
            ], style={'margin-bottom': '15px'}),
            
            html.Hr(style={'border-color': '#2a3f5f'}),
            html.Div("This will start the automated checkout process immediately.", 
                    style={'color': '#ffaa00', 'font-weight': 'bold', 'margin-top': '15px', 'text-align': 'center'})
        ])
        
        return True, confirmation_content
    
    elif button_id == 'cancel-modal-btn':
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
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_full_flow(json_data))
        loop.close()
        print(f"\n{'='*60}")
        if result['success']:
            print("Automation completed successfully!")
        else:
            print(f"Automation failed: {result.get('error')}")
        print(f"{'='*60}\n")
    
    thread = Thread(target=run_automation, daemon=True)
    thread.start()
    
    return status, True, False, False, False  # Close modal and enable payment check


# New Checkout button - restart conversation preserving details
@app.callback(
    [Output('conversation-history', 'data', allow_duplicate=True),
     Output('chat-messages', 'children', allow_duplicate=True)],
    Input('new-checkout-btn', 'n_clicks'),
    [State('json-data', 'data')],
    prevent_initial_call=True
)
def new_checkout(n_clicks, json_data):
    """Start new checkout preserving customer details"""
    if not n_clicks:
        return dash.no_update
    
    # Restart conversation agent
    conversation_agent.restart_conversation()
    
    # Get preserved URL if exists
    preserved_url = json_data.get('tasks', [{}])[0].get('url') if json_data.get('tasks') else None
    
    # Show restart message
    if preserved_url:
        restart_msg = format_message(
            f"Starting new checkout! \n\nYour previous details are preserved.\n\nWould you like to checkout with the present URL ({preserved_url[:50]}...) or provide a new URL?\n\nPlease reply with 'present' or 'new'.",
            is_user=False
        )
    else:
        restart_msg = format_message(
            "Starting new checkout! \n\nPlease provide a product URL to get started.",
            is_user=False
        )
    
    return [], [restart_msg]


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
    print(f"📱 Open: http://0.0.0.0:{APP_PORT}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    app.run(debug=True, host='0.0.0.0', port=APP_PORT)
