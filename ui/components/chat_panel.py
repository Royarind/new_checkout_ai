"""Chat Panel Component"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def create_chat_panel():
    """Create chat interface component"""
    
    return dbc.Card([
        dbc.CardHeader([
            html.H5("💬 Conversation", className="mb-0", style={'color': '#00d4ff'})
        ], style={'background-color': '#141b2d', 'border-bottom': '1px solid #2a3f5f', 'padding': '8px 12px'}),
        
        dbc.CardBody([
            # Chat messages container
            html.Div(
                id='chat-messages',
                className='chat-container',
                style={'height': '300px', 'overflow-y': 'auto', 'scroll-behavior': 'smooth'}
            ),
            
            # Input area
            dbc.InputGroup([
                dbc.Input(
                    id='chat-input',
                    placeholder='Type your message...',
                    type='text',
                    style={'background-color': '#1a2332', 'border-color': '#2a3f5f', 'color': '#fff'}
                ),
                dbc.Button(
                    '→',
                    id='send-button',
                    color='primary',
                    style={'background-color': '#00d4ff', 'border': 'none'}
                )
            ], className='mt-2')
        ], style={'background-color': '#141b2d', 'padding': '12px'})
    ], className='mb-2', style={'background-color': '#141b2d', 'border': '1px solid #2a3f5f'})


def format_message(text, is_user=True):
    """Format a chat message"""
    
    label = "You" if is_user else "CHKout.ai"
    msg_class = "user-message" if is_user else "ai-message"
    
    return html.Div([
        html.Div(label, className='message-label', style={'font-size': '11px', 'color': '#8892b0', 'margin-bottom': '4px'}),
        html.Div(text, className=f'message {msg_class}')
    ], style={'margin-bottom': '15px', 'text-align': 'right' if is_user else 'left'})
