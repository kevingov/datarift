from flask import Flask, render_template, redirect, url_for, session, request, flash, jsonify
import os
from dotenv import load_dotenv
import requests
import uuid
import json
from urllib.parse import quote_plus

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key-change-this-in-production')

# QuickBooks API Configuration
QB_CLIENT_ID = os.getenv('QB_CLIENT_ID')
QB_CLIENT_SECRET = os.getenv('QB_CLIENT_SECRET')
QB_REDIRECT_URI = os.getenv('QB_REDIRECT_URI')
QB_SANDBOX = os.getenv('QB_SANDBOX', 'False').lower() == 'true'

# QuickBooks API Endpoints
if QB_SANDBOX:
    QB_OAUTH_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"
else:
    QB_OAUTH_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DataRift - QuickBooks Integration</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .hero-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4rem 0; }
            .feature-card { transition: transform 0.3s; }
            .feature-card:hover { transform: translateY(-5px); }
        </style>
    </head>
    <body>
        <div class="hero-section text-center">
            <div class="container">
                <h1 class="display-4 fw-bold mb-4">DataRift</h1>
                <p class="lead mb-4">Seamlessly integrate with QuickBooks to pull and analyze your business data</p>
                <a href="/auth" class="btn btn-light btn-lg">Connect to QuickBooks</a>
            </div>
        </div>
        
        <div class="container my-5">
            <div class="row">
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">📊 Real-time Data</h5>
                            <p class="card-text">Access your QuickBooks data in real-time with secure OAuth integration.</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">🔒 Secure</h5>
                            <p class="card-text">Bank-level security with OAuth 2.0 authentication and encrypted data transfer.</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">⚡ Fast</h5>
                            <p class="card-text">Lightning-fast data retrieval and processing for your business insights.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

@app.route('/auth')
def auth():
    state = str(uuid.uuid4())
    session['oauth_state'] = state
    session.permanent = True

    scope = "com.intuit.quickbooks.accounting"
    auth_url = (
        f"{QB_OAUTH_AUTHORIZE_URL}?"
        f"client_id={QB_CLIENT_ID}&"
        f"scope={scope}&"
        f"redirect_uri={QB_REDIRECT_URI}&"
        f"response_type=code&"
        f"state={state}&"
        f"access_type=offline"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    received_state = request.args.get('state')
    stored_state = session.get('oauth_state')

    if received_state != stored_state:
        flash("Invalid state parameter. Please try connecting again.", "danger")
        return redirect(url_for('index'))

    code = request.args.get('code')
    realm_id = request.args.get('realmId')

    if not code or not realm_id:
        flash("Authorization failed. Missing code or realmId.", "danger")
        return redirect(url_for('index'))

    # Exchange code for tokens
    token_url = QB_OAUTH_TOKEN_URL
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + (
            requests.utils.quote(QB_CLIENT_ID) + ':' + requests.utils.quote(QB_CLIENT_SECRET)
        ).encode('base64').decode().strip()
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': QB_REDIRECT_URI
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()

        session['access_token'] = token_data['access_token']
        session['refresh_token'] = token_data['refresh_token']
        session['company_id'] = realm_id
        session['expires_in'] = token_data['expires_in']
        session['x_refresh_token_expires_in'] = token_data['x_refresh_token_expires_in']

        flash("Successfully connected to QuickBooks!", "success")
        return redirect(url_for('dashboard'))
    except requests.exceptions.RequestException as e:
        flash(f"Error exchanging token: {e}", "danger")
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'access_token' not in session or 'company_id' not in session:
        flash("Please connect to QuickBooks first.", "warning")
        return redirect(url_for('index'))
    
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DataRift Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .dashboard-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem 0; }
            .data-card { transition: transform 0.3s; }
            .data-card:hover { transform: translateY(-3px); }
        </style>
    </head>
    <body>
        <div class="dashboard-header">
            <div class="container">
                <h1 class="display-5 fw-bold">DataRift Dashboard</h1>
                <p class="lead">Your QuickBooks data at a glance</p>
            </div>
        </div>
        
        <div class="container my-4">
            <div class="row mb-4">
                <div class="col-12">
                    <button class="btn btn-primary" onclick="syncData()">🔄 Sync Data</button>
                    <a href="/" class="btn btn-outline-secondary">← Back to Home</a>
                </div>
            </div>
            
            <div class="row" id="dataCards">
                <div class="col-md-3 mb-4">
                    <div class="card data-card">
                        <div class="card-body text-center">
                            <h5 class="card-title">👥 Customers</h5>
                            <p class="card-text" id="customerCount">Loading...</p>
                            <button class="btn btn-sm btn-outline-primary" onclick="loadCustomers()">View Details</button>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="card data-card">
                        <div class="card-body text-center">
                            <h5 class="card-title">📄 Invoices</h5>
                            <p class="card-text" id="invoiceCount">Loading...</p>
                            <button class="btn btn-sm btn-outline-primary" onclick="loadInvoices()">View Details</button>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="card data-card">
                        <div class="card-body text-center">
                            <h5 class="card-title">💰 Payments</h5>
                            <p class="card-text" id="paymentCount">Loading...</p>
                            <button class="btn btn-sm btn-outline-primary" onclick="loadPayments()">View Details</button>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="card data-card">
                        <div class="card-body text-center">
                            <h5 class="card-title">📦 Items</h5>
                            <p class="card-text" id="itemCount">Loading...</p>
                            <button class="btn btn-sm btn-outline-primary" onclick="loadItems()">View Details</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5>Data Details</h5>
                        </div>
                        <div class="card-body">
                            <pre id="dataDisplay" class="bg-light p-3" style="max-height: 400px; overflow-y: auto;">Click a button above to view data...</pre>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            async function syncData() {
                try {
                    const response = await fetch('/api/sync');
                    const data = await response.json();
                    
                    document.getElementById('customerCount').textContent = data.counts.customers + ' customers';
                    document.getElementById('invoiceCount').textContent = data.counts.invoices + ' invoices';
                    document.getElementById('paymentCount').textContent = data.counts.payments + ' payments';
                    document.getElementById('itemCount').textContent = data.counts.items + ' items';
                } catch (error) {
                    console.error('Error syncing data:', error);
                }
            }
            
            async function loadCustomers() {
                try {
                    const response = await fetch('/api/customers');
                    const data = await response.json();
                    document.getElementById('dataDisplay').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('Error loading customers:', error);
                }
            }
            
            async function loadInvoices() {
                try {
                    const response = await fetch('/api/invoices');
                    const data = await response.json();
                    document.getElementById('dataDisplay').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('Error loading invoices:', error);
                }
            }
            
            async function loadPayments() {
                try {
                    const response = await fetch('/api/payments');
                    const data = await response.json();
                    document.getElementById('dataDisplay').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('Error loading payments:', error);
                }
            }
            
            async function loadItems() {
                try {
                    const response = await fetch('/api/items');
                    const data = await response.json();
                    document.getElementById('dataDisplay').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('Error loading items:', error);
                }
            }
            
            // Load initial data
            syncData();
        </script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

def make_quickbooks_api_call(query):
    if 'access_token' not in session or 'company_id' not in session:
        return {"error": "Not connected to QuickBooks"}, 401

    access_token = session['access_token']
    company_id = session['company_id']
    
    # Encode the query for URL
    encoded_query = quote_plus(query)
    
    url = f"{QB_API_BASE_URL}/{company_id}/query?query={encoded_query}&minorversion=69"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "detail": response.text}, response.status_code

@app.route('/api/customers')
def get_customers():
    data = make_quickbooks_api_call("SELECT * FROM Customer")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Customer', []))

@app.route('/api/invoices')
def get_invoices():
    data = make_quickbooks_api_call("SELECT * FROM Invoice")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Invoice', []))

@app.route('/api/payments')
def get_payments():
    data = make_quickbooks_api_call("SELECT * FROM Payment")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Payment', []))

@app.route('/api/items')
def get_items():
    data = make_quickbooks_api_call("SELECT * FROM Item")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Item', []))

@app.route('/api/sync')
def sync_data():
    customer_count = make_quickbooks_api_call("SELECT COUNT(*) FROM Customer")
    invoice_count = make_quickbooks_api_call("SELECT COUNT(*) FROM Invoice")
    item_count = make_quickbooks_api_call("SELECT COUNT(*) FROM Item")
    payment_count = make_quickbooks_api_call("SELECT COUNT(*) FROM Payment")
    
    counts = {}
    for name, data in [("customers", customer_count), ("invoices", invoice_count), 
                      ("items", item_count), ("payments", payment_count)]:
        if isinstance(data, tuple):
            counts[name] = 0
        else:
            counts[name] = data.get('QueryResponse', {}).get('totalCount', 0)
    
    return jsonify({
        "message": "Data sync completed",
        "counts": counts
    })

@app.route('/tokens')
def show_tokens():
    return {
        'access_token': session.get('access_token'),
        'refresh_token': session.get('refresh_token'),
        'company_id': session.get('company_id'),
        'expires_in': session.get('expires_in'),
        'x_refresh_token_expires_in': session.get('x_refresh_token_expires_in')
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
