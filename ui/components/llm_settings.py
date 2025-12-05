"""
LLM Settings Component (Simplified)
This component now only displays a notice that LLM configuration is loaded from the .env file.
All UI inputs for provider, API key, and model selection have been removed.
"""

import dash
import dash_bootstrap_components as dbc
from dash import html, callback, Input, Output, State

def create_llm_settings_modal():
    """Create a minimal LLM settings modal showing a static notice."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("⚙️ LLM Configuration"), style={'background-color': '#0a1929', 'color': '#00d4ff', 'border-bottom': '1px solid #2a3f5f'}),
        dbc.ModalBody([
            dbc.Alert([
                html.I(className="bi bi-info-circle me-2"),
                "LLM settings are loaded from the .env file and cannot be changed via the UI."
            ], color="info", className="mb-3"),
        ], style={'background-color': '#0a1929', 'color': '#fff'}),
        dbc.ModalFooter([
            dbc.Button("Close", id='llm-settings-close', color="secondary", className="me-2"),
        ], style={'background-color': '#0a1929', 'border-top': '1px solid #2a3f5f'})
    ], id='llm-settings-modal', size='lg', is_open=False, style={'background-color': '#0a1929'})

def create_llm_settings_button():
    """Create button to open LLM settings modal."""
    return dbc.Button([
        html.I(className="bi bi-gear me-2"), "LLM Settings"
    ], id='llm-settings-open', color="light", outline=True, size="sm", className="me-2")

# Callback to toggle modal visibility (no longer saves configuration)
@callback(
    Output('llm-settings-modal', 'is_open'),
    Input('llm-settings-open', 'n_clicks'),
    Input('llm-settings-close', 'n_clicks'),
    State('llm-settings-modal', 'is_open'),
    prevent_initial_call=True
)
def toggle_llm_settings_modal(open_clicks, close_clicks, is_open):
    """Toggle the LLM settings modal visibility."""
    ctx = dash.callback_context
    if not ctx.triggered:
        return is_open
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'llm-settings-open':
        return True
    elif button_id == 'llm-settings-close':
        return False
    return is_open
