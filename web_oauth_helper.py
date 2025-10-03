#!/usr/bin/env python3
"""
QuickBooks OAuth 2.0 Web Helper

A Flask web app that handles OAuth 2.0 flow and provides tokens
for use in Jupyter notebooks or other applications.

Deploy this to Railway and use it to get your tokens.
"""

from flask import Flask, request, redirect, render_template_string, jsonify, session
import os
import secrets
import base64
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))

class QuickBooksOAuth:
    def __init__(self):
        self.client_id = os.getenv('QB_CLIENT_ID')
        self.client_secret = os.getenv('QB_CLIENT_SECRET')
        self.sandbox = os.getenv('QB_SANDBOX', 'True').lower() == 'true'
        
        # Use Railway URL if available, otherwise localhost
        railway_url = os.getenv('RAILWAY_STATIC_URL')
        if railway_url:
            self.redirect_uri = f"https://{railway_url}/callback"
        else:
            self.redirect_uri = 'http://localhost:8000/callback'
        
        # API URLs
        if self.sandbox:
            self.base_url = "https://sandbox-quickbooks.api.intuit.com"
            self.discovery_url = "https://appcenter.intuit.com/connect/oauth2"
        else:
            self.base_url = "https://quickbooks.api.intuit.com"
            self.discovery_url = "https://appcenter.intuit.com/connect/oauth2"
        
        self.token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

oauth_helper = QuickBooksOAuth()

# HTML Templates
HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>QuickBooks OAuth Helper</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: #f5f5f5; padding: 30px; border-radius: 10px; margin: 20px 0; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .info { background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
        .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }
        .btn:hover { background: #0056b3; }
        .code-block { background: #f8f9fa; border: 1px solid #e9ecef; padding: 15px; border-radius: 5px; font-family: monospace; margin: 10px 0; }
        .token-display { background: #fff; border: 2px solid #28a745; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .copy-btn { background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 3px; cursor: pointer; margin-left: 10px; }
        .copy-btn:hover { background: #218838; }
    </style>
</head>
<body>
    <h1>🚀 QuickBooks OAuth Helper</h1>
    
    <div class="container info">
        <h2>📋 Configuration</h2>
        <p><strong>Client ID:</strong> {{ 'Set ✅' if client_id else 'Missing ❌' }}</p>
        <p><strong>Client Secret:</strong> {{ 'Set ✅' if client_secret else 'Missing ❌' }}</p>
        <p><strong>Environment:</strong> {{ '🧪 Sandbox' if sandbox else '🚀 Production' }}</p>
        <p><strong>Redirect URI:</strong> <code>{{ redirect_uri }}</code></p>
        
        {% if not client_id or not client_secret %}
        <div class="container error">
            <h3>⚠️ Missing Configuration</h3>
            <p>Please set these environment variables in Railway:</p>
            <ul>
                <li><code>QB_CLIENT_ID</code> - Your QuickBooks app client ID</li>
                <li><code>QB_CLIENT_SECRET</code> - Your QuickBooks app client secret</li>
                <li><code>QB_SANDBOX</code> - True for sandbox, False for production</li>
            </ul>
        </div>
        {% endif %}
    </div>
    
    {% if client_id and client_secret %}
    <div class="container">
        <h2>🔐 Get Your Tokens</h2>
        <p>Click the button below to authorize with QuickBooks and get your API tokens:</p>
        <a href="/auth" class="btn">🔗 Authorize with QuickBooks</a>
    </div>
    
    {% if tokens %}
    <div class="container token-display">
        <h2>✅ Your QuickBooks Tokens</h2>
        <p>Copy these tokens to use in your Jupyter notebook or application:</p>
        
        <h3>📋 For Jupyter Notebook:</h3>
        <div class="code-block">
ACCESS_TOKEN = "{{ tokens.access_token }}"<button class="copy-btn" onclick="copyToClipboard('{{ tokens.access_token }}')">Copy</button><br>
COMPANY_ID = "{{ tokens.company_id }}"<button class="copy-btn" onclick="copyToClipboard('{{ tokens.company_id }}')">Copy</button>
        </div>
        
        <h3>📊 Token Details:</h3>
        <ul>
            <li><strong>Company ID:</strong> {{ tokens.company_id }}</li>
            <li><strong>Token Type:</strong> {{ tokens.token_type }}</li>
            <li><strong>Expires In:</strong> {{ tokens.expires_in }} seconds</li>
            <li><strong>Environment:</strong> {{ '🧪 Sandbox' if sandbox else '🚀 Production' }}</li>
        </ul>
        
        <h3>🧪 Test API Connection:</h3>
        <a href="/test" class="btn">Test API Connection</a>
        
        <h3>📁 Download Tokens:</h3>
        <a href="/download" class="btn">Download tokens.txt</a>
    </div>
    {% endif %}
    
    {% endif %}
    
    <div class="container">
        <h2>📖 Instructions</h2>
        <ol>
            <li><strong>Set up your QuickBooks app:</strong> Make sure your redirect URI in the Intuit Developer Console matches: <code>{{ redirect_uri }}</code></li>
            <li><strong>Authorize:</strong> Click the "Authorize with QuickBooks" button above</li>
            <li><strong>Copy tokens:</strong> Copy the ACCESS_TOKEN and COMPANY_ID to your Jupyter notebook</li>
            <li><strong>Use in Jupyter:</strong> Paste the tokens in your notebook and run your data extraction</li>
        </ol>
    </div>
    
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert('Copied to clipboard!');
            });
        }
    </script>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Successful</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; text-align: center; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 30px; border-radius: 10px; }
        .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
    </style>
</head>
<body>
    <div class="success">
        <h1>✅ Authorization Successful!</h1>
        <p>Your QuickBooks tokens have been generated successfully.</p>
        <a href="/" class="btn">View Your Tokens</a>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    tokens = session.get('tokens')
    return render_template_string(HOME_TEMPLATE, 
                                client_id=oauth_helper.client_id,
                                client_secret=oauth_helper.client_secret,
                                sandbox=oauth_helper.sandbox,
                                redirect_uri=oauth_helper.redirect_uri,
                                tokens=tokens)

@app.route('/auth')
def auth():
    if not oauth_helper.client_id or not oauth_helper.client_secret:
        return "Missing QB_CLIENT_ID or QB_CLIENT_SECRET environment variables", 400
    
    # Generate state parameter
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Build authorization URL
    params = {
        'client_id': oauth_helper.client_id,
        'scope': 'com.intuit.quickbooks.accounting',
        'redirect_uri': oauth_helper.redirect_uri,
        'response_type': 'code',
        'state': state,
        'access_type': 'offline'
    }
    
    auth_url = f"{oauth_helper.discovery_url}?{urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    # Get parameters from callback
    auth_code = request.args.get('code')
    state = request.args.get('state')
    realm_id = request.args.get('realmId')
    error = request.args.get('error')
    
    if error:
        return f"Authorization error: {error}", 400
    
    if not auth_code or not realm_id:
        return "Missing authorization code or company ID", 400
    
    # Verify state parameter
    if state != session.get('oauth_state'):
        return "Invalid state parameter", 400
    
    # Exchange code for tokens
    tokens = exchange_code_for_tokens(auth_code, realm_id)
    
    if not tokens:
        return "Failed to exchange code for tokens", 500
    
    # Store tokens in session
    session['tokens'] = tokens
    
    return render_template_string(SUCCESS_TEMPLATE)

@app.route('/test')
def test_api():
    tokens = session.get('tokens')
    if not tokens:
        return "No tokens available. Please authorize first.", 400
    
    # Test API connection
    url = f"{oauth_helper.base_url}/v3/company/{tokens['company_id']}/query"
    headers = {
        'Authorization': f'Bearer {tokens["access_token"]}',
        'Accept': 'application/json'
    }
    params = {
        'query': 'SELECT COUNT(*) FROM CompanyInfo',
        'minorversion': '69'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "API connection successful!",
                "response": response.json()
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"API test failed: {response.status_code}",
                "response": response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"API test error: {str(e)}"
        }), 500

@app.route('/download')
def download_tokens():
    tokens = session.get('tokens')
    if not tokens:
        return "No tokens available. Please authorize first.", 400
    
    from flask import Response
    
    content = f"""# QuickBooks API Tokens
# Copy these lines into your Jupyter notebook

ACCESS_TOKEN = "{tokens['access_token']}"
COMPANY_ID = "{tokens['company_id']}"
REFRESH_TOKEN = "{tokens.get('refresh_token', '')}"

# Token Details:
# Token Type: {tokens['token_type']}
# Expires In: {tokens['expires_in']} seconds
# Environment: {"Sandbox" if oauth_helper.sandbox else "Production"}
"""
    
    return Response(
        content,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=qb_tokens.txt'}
    )

def exchange_code_for_tokens(auth_code, realm_id):
    """Exchange authorization code for access tokens"""
    
    # Create authorization header
    auth_string = f"{oauth_helper.client_id}:{oauth_helper.client_secret}"
    auth_bytes = auth_string.encode('utf-8')
    auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': oauth_helper.redirect_uri
    }
    
    try:
        response = requests.post(oauth_helper.token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            return {
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'company_id': realm_id,
                'expires_in': token_data.get('expires_in'),
                'token_type': token_data.get('token_type')
            }
        else:
            print(f"Token exchange failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error during token exchange: {str(e)}")
        return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True) 