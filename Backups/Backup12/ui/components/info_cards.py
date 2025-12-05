"""Information Cards Component"""

import dash_bootstrap_components as dbc
from dash import html
import json


def create_info_cards():
    """Create information display cards"""
    
    return html.Div([
        # Product Details Card
        dbc.Card([
            dbc.CardHeader("Product Details", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600', 'padding': '8px 12px'}),
            dbc.CardBody(id='product-info', children=[
                html.Div("No product selected yet", style={'color': '#8892b0', 'font-size': '13px'})
            ], style={'background-color': '#141b2d', 'padding': '10px'})
        ], className='mb-2', style={'border': '1px solid #2a3f5f'}),
        
        # Contact Info Card
        dbc.Card([
            dbc.CardHeader("Contact Information", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600', 'padding': '8px 12px'}),
            dbc.CardBody(id='contact-info', children=[
                html.Div("Not provided yet", style={'color': '#8892b0', 'font-size': '13px'})
            ], style={'background-color': '#141b2d', 'padding': '10px'})
        ], className='mb-2', style={'border': '1px solid #2a3f5f'}),
        
        # Shipping Address Card
        dbc.Card([
            dbc.CardHeader("Shipping Address", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600', 'padding': '8px 12px'}),
            dbc.CardBody(id='address-info', children=[
                html.Div("Not provided yet", style={'color': '#8892b0', 'font-size': '13px'})
            ], style={'background-color': '#141b2d', 'padding': '10px'})
        ], className='mb-2', style={'border': '1px solid #2a3f5f'}),
        
        # JSON Data Card (Collapsible)
        dbc.Card([
            dbc.CardHeader("JSON Data", style={'background-color': '#141b2d', 'color': '#00d4ff', 'font-weight': '600'}),
            dbc.CardBody(id='json-display', children=[
                html.Pre("{}", style={'color': '#8892b0', 'font-size': '11px', 'margin': '0'})
            ], style={'background-color': '#0a0e27', 'max-height': '120px', 'overflow-y': 'auto', 'padding': '10px'})
        ], style={'border': '1px solid #2a3f5f'})
    ])


def format_product_info(json_data):
    """Format product information"""
    tasks = json_data.get('tasks', [])
    if not tasks or not tasks[0].get('url'):
        return html.Div("No product selected yet", style={'color': '#8892b0', 'font-size': '13px'})
    
    task = tasks[0]
    variants = task.get('selectedVariant', {})
    
    variant_divs = []
    for k, v in variants.items():
        variant_divs.append(html.Div([
            html.Span(f"{k.title()}: ", style={'color': '#8892b0'}),
            html.Span(v, style={'color': '#00ff88'})
        ], style={'font-size': '12px', 'margin-bottom': '4px'}))
    
    return html.Div([
        html.Div(f"URL: {task['url'][:50]}...", style={'color': '#fff', 'font-size': '12px', 'margin-bottom': '8px'})
    ] + variant_divs + [
        html.Div([
            html.Span("Quantity: ", style={'color': '#8892b0'}),
            html.Span(str(task.get('quantity', 1)), style={'color': '#00ff88'})
        ], style={'font-size': '12px'})
    ])


def format_contact_info(json_data):
    """Format contact information"""
    contact = json_data.get('customer', {}).get('contact', {})
    if not contact:
        return html.Div("Not provided yet", style={'color': '#8892b0', 'font-size': '13px'})
    
    contact_divs = []
    for k, v in contact.items():
        contact_divs.append(html.Div([
            html.Span(f"{k.title()}: ", style={'color': '#8892b0'}),
            html.Span(v or 'N/A', style={'color': '#fff'})
        ], style={'font-size': '12px', 'margin-bottom': '4px'}))
    
    return html.Div(contact_divs)


def format_address_info(json_data):
    """Format shipping address"""
    address = json_data.get('customer', {}).get('shippingAddress', {})
    if not address:
        return html.Div("Not provided yet", style={'color': '#8892b0', 'font-size': '13px'})
    
    return html.Div([
        html.Div(address.get('addressLine1', ''), style={'color': '#fff', 'font-size': '12px', 'margin-bottom': '4px'}),
        html.Div(f"{address.get('city', '')}, {address.get('province', '')} {address.get('postalCode', '')}", 
                 style={'color': '#fff', 'font-size': '12px'})
    ])
