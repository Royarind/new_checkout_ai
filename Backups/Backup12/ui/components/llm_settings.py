"""
LLM Settings Component
UI for configuring LLM providers
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def create_llm_settings_modal():
    """Create LLM settings modal"""
    
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("⚙️ LLM Configuration"), style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody([
            # Info alert
            dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                "Configure your LLM provider. API keys are used for this session only and never stored on our servers."
            ], color="info", className="mb-3"),
            
            # Provider selection
            html.Div([
                html.Label("Provider", className="fw-bold mb-2"),
                dcc.Dropdown(
                    id='llm-provider-dropdown',
                    options=[
                        {'label': 'OpenAI', 'value': 'openai'},
                        {'label': 'Groq', 'value': 'groq'},
                        {'label': 'Anthropic Claude', 'value': 'anthropic'},
                        {'label': 'Google Gemini', 'value': 'gemini'},
                        {'label': 'Azure OpenAI', 'value': 'azure'},
                        {'label': 'Custom Endpoint', 'value': 'custom'}
                    ],
                    value='openai',
                    clearable=False,
                    className="mb-3",
                    style={'background-color': '#141b2d', 'color': '#00d4ff'}
                )
            ]),
            
            # API Key input
            html.Div([
                html.Label("API Key", className="fw-bold mb-2"),
                dbc.InputGroup([
                    dbc.Input(
                        id='llm-api-key-input',
                        type='password',
                        placeholder='Enter your API key...'
                    ),
                    dbc.Button(
                        html.I(className="bi bi-eye"),
                        id='llm-api-key-toggle',
                        color="secondary",
                        outline=True
                    )
                ], className="mb-3")
            ]),
            
            # Model selection
            html.Div([
                html.Label("Model", className="fw-bold mb-2"),
                dcc.Dropdown(
                    id='llm-model-dropdown',
                    placeholder='Select a model...',
                    clearable=False,
                    className="mb-2",
                    style={'background-color': '#141b2d', 'color': '#00d4ff'}
                ),
                html.Small("OR", className="text-muted d-block text-center mb-2"),
                dbc.Input(
                    id='llm-custom-model-input',
                    type='text',
                    placeholder='Custom model name (e.g., gpt-4-0125-preview)',
                    className="mb-3"
                )
            ]),
            
            # Advanced settings (collapsible)
            dbc.Accordion([
                dbc.AccordionItem([
                    html.Div([
                        html.Label("Temperature", className="fw-bold mb-2"),
                        dcc.Slider(
                            id='llm-temperature-slider',
                            min=0,
                            max=2,
                            step=0.1,
                            value=0.7,
                            marks={0: '0', 0.5: '0.5', 1: '1', 1.5: '1.5', 2: '2'},
                            tooltip={"placement": "bottom", "always_visible": True}
                        )
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("Max Tokens", className="fw-bold mb-2"),
                        dbc.Input(
                            id='llm-max-tokens-input',
                            type='number',
                            value=1024,
                            min=1,
                            max=4096
                        )
                    ])
                ], title="Advanced Settings")
            ], start_collapsed=True, className="mb-3"),
            
            # Azure-specific config (hidden by default)
            html.Div([
                html.Hr(),
                html.Label("Azure Configuration", className="fw-bold mb-2"),
                dbc.Input(
                    id='llm-azure-endpoint-input',
                    type='text',
                    placeholder='Endpoint URL (e.g., https://your-resource.openai.azure.com)',
                    className="mb-2"
                ),
                dbc.Input(
                    id='llm-azure-deployment-input',
                    type='text',
                    placeholder='Deployment Name',
                    className="mb-3"
                )
            ], id='llm-azure-config', style={'display': 'none'}),
            
            # Custom endpoint config (hidden by default)
            html.Div([
                html.Hr(),
                html.Label("Custom Endpoint Configuration", className="fw-bold mb-2"),
                dbc.Input(
                    id='llm-custom-base-url-input',
                    type='text',
                    placeholder='Base URL (e.g., http://localhost:11434/v1)',
                    className="mb-3"
                )
            ], id='llm-custom-config', style={'display': 'none'}),
            
            # Test connection section
            html.Hr(),
            html.Div([
                dbc.Button(
                    [html.I(className="bi bi-lightning-charge me-2"), "Test Connection"],
                    id='llm-test-button',
                    color="primary",
                    className="me-2"
                ),
                dbc.Spinner(
                    html.Div(id='llm-test-spinner'),
                    size="sm",
                    color="primary"
                )
            ], className="d-flex align-items-center mb-3"),
            
            # Test result
            dbc.Alert(
                id='llm-test-result',
                children="Click 'Test Connection' to verify your configuration",
                color="secondary",
                className="mb-0"
            )
        ], style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("Close", id='llm-settings-close', color="secondary", className="me-2"),
            dbc.Button(
                [html.I(className="bi bi-check-circle me-2"), "Save & Use"],
                id='llm-save-button',
                color="success"
            )
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='llm-settings-modal', size='lg', is_open=False, style={'background-color': '#0a1929'})


def create_llm_settings_button():
    """Create button to open LLM settings"""
    return dbc.Button(
        [html.I(className="bi bi-gear me-2"), "LLM Settings"],
        id='llm-settings-open',
        color="light",
        outline=True,
        size="sm",
        className="me-2"
    )


# Callback to toggle API key visibility
from dash import callback, Input, Output, State

@callback(
    Output('llm-api-key-input', 'type'),
    Output('llm-api-key-toggle', 'children'),
    Input('llm-api-key-toggle', 'n_clicks'),
    State('llm-api-key-input', 'type'),
    prevent_initial_call=True
)
def toggle_api_key_visibility(n_clicks, current_type):
    """Toggle between password and text for API key"""
    if current_type == 'password':
        return 'text', html.I(className="bi bi-eye-slash")
    else:
        return 'password', html.I(className="bi bi-eye")


@callback(
    Output('llm-settings-modal', 'is_open'),
    Input('llm-settings-open', 'n_clicks'),
    Input('llm-settings-close', 'n_clicks'),
    Input('llm-save-button', 'n_clicks'),
    State('llm-settings-modal', 'is_open'),
    State('llm-provider-dropdown', 'value'),
    State('llm-api-key-input', 'value'),
    State('llm-model-dropdown', 'value'),
    State('llm-custom-model-input', 'value'),
    State('llm-temperature-slider', 'value'),
    State('llm-max-tokens-input', 'value'),
    prevent_initial_call=True
)
def toggle_llm_settings_modal(open_clicks, close_clicks, save_clicks, is_open, 
                              provider, api_key, model_dropdown, custom_model, temperature, max_tokens):
    """Toggle LLM settings modal and save config on Save button"""
    from dash import callback_context
    
    ctx = callback_context
    if not ctx.triggered:
        return is_open
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Save configuration when Save button is clicked
    if button_id == 'llm-save-button':
        from ui.api.llm_config_api import set_session_llm_config
        
        config = {
            'provider': provider,
            'api_key': api_key.strip() if api_key else '',
            'model': custom_model if custom_model else model_dropdown,
            'temperature': temperature or 0.7,
            'max_tokens': max_tokens or 1024
        }
        
        set_session_llm_config(config)
        print(f"LLM config saved: {provider} - {config['model']}")
    
    return not is_open
