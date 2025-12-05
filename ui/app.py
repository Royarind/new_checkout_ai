"""CHKout.ai - Main Dash Application"""

# CRITICAL: Fix encoding BEFORE any other imports (Windows compatibility)
import sys
import os

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

import dash
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import json
import asyncio
from threading import Thread

# Import project-specific modules after path setup
from config import COLORS, APP_TITLE, APP_PORT, SCREENSHOT_INTERVAL
from components.chat_panel import create_chat_panel, format_message
from components.info_cards import create_info_cards, format_product_info, format_contact_info, format_address_info
from components.llm_settings import create_llm_settings_modal, create_llm_settings_button
from services.conversation_agent import ConversationAgent
from services.screenshot_service import ScreenshotService
from main_orchestrator import run_full_flow

# Import LLM config API to register callbacks - this enables AI model settings
import ui.api.llm_config_api

# Add parent directory to path to access project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def setup_project_path():
    """Dynamically find and add project root to sys.path"""
    # Get current directory where this script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Dynamic Search: Walk up directory tree until we find 'agents' directory
    # This helps the program find necessary project files regardless of where it's run from
    search_dir = current_dir
    while search_dir != os.path.dirname(search_dir):  # Stop when we reach root directory
        if os.path.exists(os.path.join(search_dir, 'agents')):
            if search_dir not in sys.path:
                sys.path.insert(0, search_dir)
                print(f"DEBUG: Found project root at: {search_dir}")
            return
        search_dir = os.path.dirname(search_dir)  # Move up one directory level
    
    # 2. Fallback: Check standard development location
    # This fixes issues when running from Trash/Backups where relative paths are broken
    dev_path = os.path.expanduser("~/Documents/Checkout_ai")
    if os.path.exists(os.path.join(dev_path, 'agents')):
        if dev_path not in sys.path:
            sys.path.insert(0, dev_path)
            print(f"DEBUG: Using fallback project root: {dev_path}")
        return
        
    print("DEBUG: Warning - Could not find project root containing 'agents'")

# Call the function to set up proper file paths
setup_project_path()


# Initialize the main Dash web application
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],  # Use Bootstrap for styling
    suppress_callback_exceptions=True,  # Allow flexible callback definitions
    use_async=True  # Enable asynchronous operations for better performance
)
app.title = APP_TITLE  # Set the browser tab title

# Global services that manage conversation and screenshots throughout the app
conversation_agent = ConversationAgent()  # Handles AI conversations
screenshot_service = ScreenshotService()  # Captures browser screenshots
automation_page = None  # Store page reference for screenshots

def get_conversation_agent():
    """Get the global conversation agent instance"""
    return conversation_agent

# Add custom CSS for dropdown styling to match the app's color scheme
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

# Layout defines the visual structure of the web application
app.layout = dbc.Container([
    # Header section with app title and control buttons
    dbc.Row([
        dbc.Col([
            html.H2([
                html.Span("CHK", style={'color': '#00d4ff'}),  # Blue CHK
                html.Span("out.ai", style={'color': '#fff'})   # White out.ai
            ], className='mb-0'),
            html.P("Intelligent Conversational Checkout", style={'color': '#8892b0', 'font-size': '14px', 'margin': '0'})
        ], width=8),  # Takes 8/12 of width for title
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
                create_llm_settings_button(),  # Button to open AI settings
                html.Div(id='status-indicator', children=[
                    html.Span("● ", style={'color': '#00ff88', 'font-size': '20px'}),  # Green dot
                    html.Span("Ready", style={'color': '#00ff88'})  # Status text
                ], style={'display': 'inline-block'})
            ], style={'text-align': 'right', 'padding-top': '10px'})
        ], width=4)  # Takes 4/12 of width for buttons
    ], className='mb-2', style={'padding': '10px 0', 'border-bottom': '1px solid #2a3f5f'}),
    
    # Main content area divided into two columns
    dbc.Row([
        # Left panel - Shows live browser view and control buttons
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
            
            # Control buttons for checkout actions
            dbc.ButtonGroup([
                dbc.Button("Edit Details", id='quick-buy-btn', color='primary', disabled=True, style={'font-weight': '600'}),
                dbc.Button("Quick Checkout", id='start-btn', color='success', disabled=True, style={'font-weight': '600'}),
                dbc.Button("Start Over", id='reset-btn', color='warning', style={'font-weight': '600'})
            ], style={'width': '100%'})
        ], width=6),  # Left panel takes half the width
        
        # Right panel - Chat interface and information cards
        dbc.Col([
            create_chat_panel(),  # Chat area where user interacts with AI
            create_info_cards()   # Cards showing product, contact, and address info
        ], width=6)  # Right panel takes half the width
    ]),
    
    # Hidden stores that hold application data behind the scenes
    dcc.Store(id='conversation-history', data=[]),  # Stores chat history
    dcc.Store(id='json-data', data={'tasks': []}),  # Stores all checkout data
    dcc.Interval(id='screenshot-interval', interval=SCREENSHOT_INTERVAL, disabled=True),  # Timer for updating screenshots
    dcc.Interval(id='payment-check-interval', interval=2000, disabled=True),  # Timer for checking payment status
    
    # LLM Settings Modal - Popup for configuring AI model settings
    create_llm_settings_modal(),
    
    # Confirmation Modal - Popup to confirm purchase before starting automation
    dbc.Modal([
        dbc.ModalHeader("Confirm Purchase Details", style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody(id='confirm-modal-body', style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("Edit Details", id='edit-details-btn', color='info', style={'font-weight': '600'}),
            dbc.Button("✓ Confirm & Start", id='confirm-start-btn', color='success', style={'font-weight': '600'}),
            dbc.Button("Cancel", id='cancel-modal-btn', color='secondary')
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='confirm-modal', is_open=False, size='lg', style={'background-color': '#0a1929'}),
    
    # Edit Details Modal - Popup for modifying checkout information
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


# Clientside callback for auto-scroll - automatically scrolls chat to newest message
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

# Callbacks define how the app responds to user interactions
@app.callback(
    [Output('chat-messages', 'children'),  # Update chat display
     Output('conversation-history', 'data'),  # Update stored history
     Output('json-data', 'data'),  # Update checkout data
     Output('chat-input', 'value'),  # Clear input field
     Output('product-info', 'children'),  # Update product info card
     Output('contact-info', 'children'),  # Update contact info card
     Output('address-info', 'children'),  # Update address info card
     Output('json-display', 'children'),  # Update raw JSON display
     Output('start-btn', 'disabled'),  # Enable/disable start button
     Output('quick-buy-btn', 'disabled')],  # Enable/disable quick buy button
    [Input('send-button', 'n_clicks'),  # Trigger when send button clicked
     Input('chat-input', 'n_submit')],  # Trigger when Enter pressed in chat
    [State('chat-input', 'value'),  # Get current message text
     State('conversation-history', 'data'),  # Get previous chat history
     State('json-data', 'data')]  # Get current checkout data
)
async def handle_chat(n_clicks, n_submit, message, history, json_data):
    """Handle chat messages from user and process with AI"""
    
    # Don't process empty messages
    if not message or not message.strip():
        return dash.no_update
    
    # Add user message to conversation history
    history.append({'role': 'user', 'content': message})
    
    # Send message to AI conversation agent and get response
    response = await conversation_agent.process_message(message)
    
    # Add AI response to conversation history
    history.append({'role': 'assistant', 'content': response['message']})
    
    # Update JSON data with any new information from AI
    json_data = response['json_data']
    
    # Format all messages for display in chat
    messages = []
    for msg in history:
        is_user = msg['role'] == 'user'
        messages.append(format_message(msg['content'], is_user))
    
    # Update information cards with latest data
    product_info = format_product_info(json_data)
    contact_info = format_contact_info(json_data)
    address_info = format_address_info(json_data)
    json_display = html.Pre(json.dumps(json_data, indent=2), 
                           style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
    
    # Validate JSON completeness - check if all required fields are filled
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
    
    # Find which fields are still missing
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
    
    # Print validation status for debugging
    print(f"\n{'='*60}")
    print(f"UI VALIDATION: {'COMPLETE' if all_complete else 'INCOMPLETE'}")
    print(f"Missing fields: {missing if missing else 'None'}")
    print(f"Start button: {'ENABLED' if not start_disabled else 'DISABLED'}")
    print(f"{'='*60}\n")
    
    # Return all updated components
    return messages, history, json_data, '', product_info, contact_info, address_info, json_display, start_disabled, start_disabled


# Initialize with welcome message when app starts
@app.callback(
    Output('chat-messages', 'children', allow_duplicate=True),
    Input('chat-messages', 'id'),
    prevent_initial_call='initial_duplicate'
)
def initialize_chat(_):
    """Show welcome message when chat first loads"""
    welcome = format_message(
        "Hi! I'm CHKout.ai!! \n\nI'll help you automate your checkout process. "
        "Just share the product URL to get started!...You can copy the URL and paste it here!\n\n",
        is_user=False
    )
    return [welcome]


# Start automation when user clicks Quick Checkout button
@app.callback(
    [Output('status-indicator', 'children'),  # Update status indicator
     Output('start-btn', 'disabled', allow_duplicate=True),  # Disable start button
     Output('screenshot-interval', 'disabled'),  # Enable screenshot updates
     Output('payment-check-interval', 'disabled', allow_duplicate=True)],  # Enable payment checking
    Input('start-btn', 'n_clicks'),  # Trigger when start button clicked
    State('json-data', 'data'),  # Get current checkout data
    prevent_initial_call=True
)
def start_automation(n_clicks, json_data):
    """Start the automation backend process"""
    if not n_clicks:
        return dash.no_update
    
    # Validate and fix JSON data format before starting automation
    print("\n" + "="*60, flush=True)
    print("VALIDATING JSON DATA BEFORE AUTOMATION", flush=True)
    print("="*60, flush=True)
    print(json.dumps(json_data, indent=2), flush=True)
    sys.stdout.flush()
    
    # Ensure proper JSON structure exists
    if 'customer' not in json_data:
        print("ERROR: Missing 'customer' key")
        return dash.no_update
    
    if 'tasks' not in json_data or not json_data['tasks']:
        print("ERROR: Missing 'tasks' key")
        return dash.no_update
    
    # Validate customer data structure
    customer = json_data['customer']
    if 'contact' not in customer:
        print("ERROR: Missing 'contact' in customer")
        return dash.no_update
    
    if 'shippingAddress' not in customer:
        print("ERROR: Missing 'shippingAddress' in customer")
        return dash.no_update
    
    # Ensure all required fields exist with proper values
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
    
    # Ensure optional fields exist (can be empty)
    if 'phone' not in contact:
        contact['phone'] = ''
    
    if 'addressLine2' not in address:
        address['addressLine2'] = ''
    
    if 'country' not in address:
        address['country'] = 'US'
    
    if 'selectedVariant' not in task:
        task['selectedVariant'] = {}
    
    if 'options' not in task:
        task['options'] = [{'name': '', 'values': []}]
    
    if 'metadata' not in task:
        task['metadata'] = {'title': '', 'description': '', 'primaryImage': '', 'price': ''}
    
    if 'shippingMethod' not in customer:
        customer['shippingMethod'] = {'strategy': 'cheapest'}
    
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
    
    # Update status indicator to show automation is running
    status = html.Div([
        html.Span("● ", style={'color': '#ffaa00', 'font-size': '20px'}),  # Yellow dot
        html.Span("Running...", style={'color': '#ffaa00'})  # Yellow text
    ], style={'text-align': 'right', 'padding-top': '10px'})
    
    # Start automation in background thread so web app remains responsive
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
    
    return status, True, False, False  # Enable screenshot and payment check intervals


# Update browser screenshot at regular intervals
@app.callback(
    Output('browser-view', 'children'),
    Input('screenshot-interval', 'n_intervals')
)
def update_screenshot(n):
    """Update browser screenshot display with latest image"""
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


# Check if payment page is reached and notify user
@app.callback(
    [Output('chat-messages', 'children', allow_duplicate=True),  # Add payment message
     Output('payment-check-interval', 'disabled')],  # Disable further checking
    Input('payment-check-interval', 'n_intervals'),  # Trigger every 2 seconds
    State('chat-messages', 'children'),  # Get current messages
    prevent_initial_call=True
)
def check_payment_ready(n, current_messages):
    """Check if payment page is reached and notify user"""
    notification_file = '/tmp/chkout_payment_ready.txt'
    
    # Check if automation has signaled that payment page is ready
    if os.path.exists(notification_file):
        # Delete notification file to prevent duplicate messages
        try:
            os.remove(notification_file)
        except:
            pass
        
        # Add payment ready message to chat
        payment_message = format_message(
            "SUCCESS! All automation steps completed!\n\n"
            "Product added to cart\n"
            "Variants selected\n"
            "Shipping information filled\n"
            "Payment page reached\n\n"
            "Your order is ready! Please complete the payment in the browser to finalize your purchase.",
            is_user=False
        )
        
        # Add payment message to existing messages
        if current_messages:
            return current_messages + [payment_message], True
        return [payment_message], True
    
    return dash.no_update, dash.no_update


# Edit modal callbacks - handle opening/closing and populating the edit form
@app.callback(
    [Output('edit-modal', 'is_open'),  # Open/close edit modal
     Output('edit-quantity', 'value'),  # Populate quantity field
     Output('edit-variant-color', 'value'),  # Populate color field
     Output('edit-variant-size', 'value'),  # Populate size field
     Output('edit-email', 'value'),  # Populate email field
     Output('edit-password', 'value'),  # Populate password field
     Output('edit-firstName', 'value'),  # Populate first name field
     Output('edit-lastName', 'value'),  # Populate last name field
     Output('edit-phone', 'value'),  # Populate phone field
     Output('edit-address', 'value'),  # Populate address field
     Output('edit-city', 'value'),  # Populate city field
     Output('edit-province', 'value'),  # Populate province field
     Output('edit-postal', 'value'),  # Populate postal code field
     Output('confirm-modal', 'is_open', allow_duplicate=True)],  # Close confirmation modal
    [Input('edit-details-btn', 'n_clicks'),  # Trigger when edit button clicked
     Input('edit-cancel-btn', 'n_clicks')],  # Trigger when cancel button clicked
    [State('json-data', 'data'),  # Get current checkout data
     State('edit-modal', 'is_open')],  # Get current modal state
    prevent_initial_call=True
)
def toggle_edit_modal(edit_clicks, cancel_clicks, json_data, is_open):
    """Open/close edit modal and populate fields with current data"""
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    
    # Determine which button was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'edit-details-btn':
        # Extract current data from JSON
        task = json_data.get('tasks', [{}])[0]
        contact = json_data.get('customer', {}).get('contact', {})
        address = json_data.get('customer', {}).get('shippingAddress', {})
        variants = task.get('selectedVariant', {})
        
        # Open modal and populate all fields with current values
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
        # Close modal without saving
        return (False,) + (dash.no_update,) * 12
    
    return dash.no_update


# Save edited details from modal back to JSON data
@app.callback(
    [Output('json-data', 'data', allow_duplicate=True),  # Update JSON data
     Output('edit-modal', 'is_open', allow_duplicate=True),  # Close edit modal
     Output('confirm-modal', 'is_open', allow_duplicate=True),  # Open confirmation modal
     Output('product-info', 'children', allow_duplicate=True),  # Update product info
     Output('contact-info', 'children', allow_duplicate=True),  # Update contact info
     Output('address-info', 'children', allow_duplicate=True),  # Update address info
     Output('json-display', 'children', allow_duplicate=True),  # Update JSON display
     Output('confirm-modal-body', 'children', allow_duplicate=True)],  # Update confirmation content
    Input('edit-save-btn', 'n_clicks'),  # Trigger when save button clicked
    [State('edit-quantity', 'value'),  # Get edited quantity
     State('edit-variant-color', 'value'),  # Get edited color
     State('edit-variant-size', 'value'),  # Get edited size
     State('edit-email', 'value'),  # Get edited email
     State('edit-password', 'value'),  # Get edited password
     State('edit-firstName', 'value'),  # Get edited first name
     State('edit-lastName', 'value'),  # Get edited last name
     State('edit-phone', 'value'),  # Get edited phone
     State('edit-address', 'value'),  # Get edited address
     State('edit-city', 'value'),  # Get edited city
     State('edit-province', 'value'),  # Get edited province
     State('edit-postal', 'value'),  # Get edited postal code
     State('json-data', 'data')],  # Get current JSON data
    prevent_initial_call=True
)
def save_edited_details(n_clicks, quantity, color, size, email, password, firstName, lastName, phone, address, city, province, postal, json_data):
    """Save edited details to JSON and update all displays"""
    if not n_clicks:
        return dash.no_update
    
    # Update JSON with edited values
    if 'customer' not in json_data:
        json_data['customer'] = {}
    
    if 'tasks' not in json_data or not json_data['tasks']:
        json_data['tasks'] = [{}]
    
    # Update product/task information
    json_data['tasks'][0]['quantity'] = quantity if quantity else 1
    
    # Update product variants
    variants = {}
    if color:
        variants['color'] = color
    if size:
        variants['size'] = size
    json_data['tasks'][0]['selectedVariant'] = variants
    
    # Update contact information
    json_data['customer']['contact'] = {
        'email': email,
        'password': password if password else '',
        'firstName': firstName,
        'lastName': lastName,
        'phone': phone
    }
    
    # Update shipping address
    json_data['customer']['shippingAddress'] = {
        'addressLine1': address,
        'city': city,
        'province': province,
        'postalCode': postal,
        'country': json_data.get('customer', {}).get('shippingAddress', {}).get('country', 'US')
    }
    
    print("Details updated:", json.dumps(json_data, indent=2))
    
    # Update all information displays with new data
    product_info = format_product_info(json_data)
    contact_info = format_contact_info(json_data)
    address_info = format_address_info(json_data)
    json_display = html.Pre(json.dumps(json_data, indent=2), 
                           style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
    
    # Update confirmation modal body with new details
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
    
    # Close edit modal and reopen confirmation modal with updated details
    return json_data, False, True, product_info, contact_info, address_info, json_display, confirmation_content


# Quick Buy button - show confirmation modal with current details
@app.callback(
    [Output('confirm-modal', 'is_open'),  # Open/close confirmation modal
     Output('confirm-modal-body', 'children')],  # Set modal content
    [Input('quick-buy-btn', 'n_clicks'),  # Trigger when quick buy clicked
     Input('cancel-modal-btn', 'n_clicks')],  # Trigger when cancel clicked
    [State('json-data', 'data'),  # Get current checkout data
     State('confirm-modal', 'is_open')],  # Get current modal state
    prevent_initial_call=True
)
def toggle_confirmation_modal(quick_clicks, cancel_clicks, json_data, is_open):
    """Show/hide confirmation modal with purchase details"""
    ctx = callback_context
    if not ctx.triggered:
        return False, ""
    
    # Determine which button was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'quick-buy-btn':
        # Build confirmation display with current data
        task = json_data.get('tasks', [{}])[0]
        contact = json_data.get('customer', {}).get('contact', {})
        address = json_data.get('customer', {}).get('shippingAddress', {})
        
        # Format product variants for display
        variants = task.get('selectedVariant', {})
        variant_str = ', '.join([f"{k}: {v}" for k, v in variants.items() if k != '__user_specified__']) if variants else 'None'
        
        # Create detailed confirmation content
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
        # Close modal without starting automation
        return False, ""
    
    return is_open, ""


# Confirm and start automation from modal
@app.callback(
    [Output('status-indicator', 'children', allow_duplicate=True),  # Update status
     Output('start-btn', 'disabled', allow_duplicate=True),  # Disable start button
     Output('screenshot-interval', 'disabled', allow_duplicate=True),  # Enable screenshots
     Output('confirm-modal', 'is_open', allow_duplicate=True),  # Close confirmation modal
     Output('payment-check-interval', 'disabled', allow_duplicate=True)],  # Enable payment checking
    Input('confirm-start-btn', 'n_clicks'),  # Trigger when confirm button clicked
    State('json-data', 'data'),  # Get current checkout data
    prevent_initial_call=True
)
def confirm_and_start(n_clicks, json_data):
    """Start automation after user confirms purchase details"""
    if not n_clicks:
        return dash.no_update
    
    # Update status indicator to show automation is running
    status = html.Div([
        html.Span("● ", style={'color': '#ffaa00', 'font-size': '20px'}),  # Yellow dot
        html.Span("Running...", style={'color': '#ffaa00'})  # Yellow text
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


# New Checkout button - restart conversation preserving customer details
@app.callback(
    [Output('conversation-history', 'data', allow_duplicate=True),  # Clear chat history
     Output('chat-messages', 'children', allow_duplicate=True)],  # Show restart message
    Input('new-checkout-btn', 'n_clicks'),  # Trigger when new checkout clicked
    [State('json-data', 'data')],  # Get current checkout data
    prevent_initial_call=True
)
def new_checkout(n_clicks, json_data):
    """Start new checkout preserving customer details but clearing product info"""
    if not n_clicks:
        return dash.no_update
    
    # Restart conversation agent (clears AI memory)
    conversation_agent.restart_conversation()
    
    # Get preserved URL if exists (for convenience)
    preserved_url = json_data.get('tasks', [{}])[0].get('url') if json_data.get('tasks') else None
    
    # Show appropriate restart message based on whether URL exists
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


# Reset/Start Over Fresh button - completely clear everything
@app.callback(
    [Output('conversation-history', 'data', allow_duplicate=True),  # Clear history
     Output('json-data', 'data', allow_duplicate=True),  # Clear JSON data
     Output('chat-messages', 'children', allow_duplicate=True),  # Show welcome message
     Output('browser-view', 'children', allow_duplicate=True)],  # Clear browser view
    Input('reset-btn', 'n_clicks'),  # Trigger when reset button clicked
    prevent_initial_call=True
)
def reset_conversation(n_clicks):
    """Reset conversation and delete saved profile - complete fresh start"""
    if not n_clicks:
        return dash.no_update
    
    # Delete saved user profile from file system
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
    
    # Reset conversation agent (clears all AI memory)
    conversation_agent.reset()
    
    # Show welcome message as if starting for first time
    welcome = format_message(
        "Hi! I'm CHKout.ai 👋\n\nI'll help you automate your checkout process. "
        "Just share a product URL to get started!",
        is_user=False
    )
    
    # Clear browser view to show placeholder
    browser_placeholder = html.Div(
        "Browser will appear here when automation starts",
        style={'color': '#8892b0', 'text-align': 'center', 'padding': '100px 20px'}
    )
    
    return [], {'tasks': []}, [welcome], browser_placeholder


# Main entry point - start the web server
if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"CHKout.ai Starting...")
    print(f"{'='*60}")
    print(f"Open: http://localhost:{APP_PORT}")
    print(f"{'='*60}\n")
    sys.stdout.flush()
    
    # Start the Dash web application
    app.run(debug=True, host='0.0.0.0', port=APP_PORT)