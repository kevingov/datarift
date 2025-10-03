#!/usr/bin/env python3
"""
QuickBooks OAuth 2.0 Helper

This script runs a temporary web server to handle the OAuth 2.0 flow
and extract access tokens for use in Jupyter notebooks.

Usage:
1. Make sure your .env file has QB_CLIENT_ID and QB_CLIENT_SECRET
2. Run: python qb_oauth_helper.py
3. Follow the instructions to authorize
4. Copy the tokens to your Jupyter notebook
"""

import os
import secrets
import base64
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OAuthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""
    
    def do_GET(self):
        """Handle GET requests (OAuth callback)"""
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == '/callback':
            # Parse query parameters
            query_params = parse_qs(parsed_url.query)
            
            # Extract authorization code and state
            auth_code = query_params.get('code', [None])[0]
            state = query_params.get('state', [None])[0]
            realm_id = query_params.get('realmId', [None])[0]
            
            if auth_code and realm_id:
                # Store the results in the server instance
                self.server.auth_code = auth_code
                self.server.realm_id = realm_id
                self.server.state = state
                self.server.success = True
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                success_html = """
                <html>
                <head><title>QuickBooks Authorization Success</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ Authorization Successful!</h1>
                    <p>You can now close this window and return to your terminal.</p>
                    <p>Your tokens are being processed...</p>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
            else:
                # Send error response
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                error_html = """
                <html>
                <head><title>QuickBooks Authorization Error</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: red;">❌ Authorization Failed</h1>
                    <p>Missing authorization code or company ID.</p>
                    <p>Please try again.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
        else:
            # Handle other paths
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

class QuickBooksOAuth:
    """QuickBooks OAuth 2.0 helper class"""
    
    def __init__(self):
        self.client_id = os.getenv('QB_CLIENT_ID')
        self.client_secret = os.getenv('QB_CLIENT_SECRET')
        self.sandbox = os.getenv('QB_SANDBOX', 'True').lower() == 'true'
        self.redirect_uri = 'http://localhost:8080/callback'
        
        # API URLs
        if self.sandbox:
            self.base_url = "https://sandbox-quickbooks.api.intuit.com"
            self.discovery_url = "https://appcenter.intuit.com/connect/oauth2"
        else:
            self.base_url = "https://quickbooks.api.intuit.com"
            self.discovery_url = "https://appcenter.intuit.com/connect/oauth2"
        
        self.token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        
        # OAuth state
        self.state = None
        self.server = None
        
    def validate_config(self):
        """Validate OAuth configuration"""
        if not self.client_id:
            print("❌ QB_CLIENT_ID not found in .env file")
            return False
        
        if not self.client_secret:
            print("❌ QB_CLIENT_SECRET not found in .env file")
            return False
        
        print("✅ OAuth configuration valid")
        print(f"   Client ID: {self.client_id[:10]}...")
        print(f"   Environment: {'🧪 Sandbox' if self.sandbox else '🚀 Production'}")
        return True
    
    def generate_auth_url(self):
        """Generate QuickBooks OAuth authorization URL"""
        self.state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': self.client_id,
            'scope': 'com.intuit.quickbooks.accounting',
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'state': self.state,
            'access_type': 'offline'
        }
        
        auth_url = f"{self.discovery_url}?{urlencode(params)}"
        return auth_url
    
    def start_callback_server(self):
        """Start temporary HTTP server to handle OAuth callback"""
        try:
            self.server = HTTPServer(('localhost', 8080), OAuthHandler)
            self.server.auth_code = None
            self.server.realm_id = None
            self.server.state = None
            self.server.success = False
            
            print("🌐 Starting callback server on http://localhost:8080")
            
            # Start server in a separate thread
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start callback server: {str(e)}")
            print("   Make sure port 8080 is available")
            return False
    
    def wait_for_callback(self, timeout=300):
        """Wait for OAuth callback with timeout"""
        print("⏳ Waiting for authorization callback...")
        print("   (This will timeout in 5 minutes)")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.server and self.server.success:
                return {
                    'auth_code': self.server.auth_code,
                    'realm_id': self.server.realm_id,
                    'state': self.server.state
                }
            time.sleep(1)
        
        print("⏰ Timeout waiting for authorization")
        return None
    
    def exchange_code_for_tokens(self, auth_code, realm_id):
        """Exchange authorization code for access tokens"""
        print("🔄 Exchanging authorization code for tokens...")
        
        # Create authorization header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            
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
                print(f"❌ Token exchange failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error during token exchange: {str(e)}")
            return None
    
    def test_api_connection(self, access_token, company_id):
        """Test the API connection with the new tokens"""
        print("🧪 Testing API connection...")
        
        url = f"{self.base_url}/v3/company/{company_id}/query"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        params = {
            'query': 'SELECT COUNT(*) FROM CompanyInfo',
            'minorversion': '69'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                print("✅ API connection successful!")
                return True
            else:
                print(f"❌ API test failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ API test error: {str(e)}")
            return False
    
    def save_tokens(self, tokens):
        """Save tokens to file for easy copying"""
        try:
            with open('qb_tokens.txt', 'w') as f:
                f.write("# QuickBooks API Tokens\n")
                f.write("# Copy these lines into your Jupyter notebook\n\n")
                f.write(f'ACCESS_TOKEN = "{tokens["access_token"]}"\n')
                f.write(f'COMPANY_ID = "{tokens["company_id"]}"\n')
                f.write(f'REFRESH_TOKEN = "{tokens["refresh_token"]}"\n\n')
                f.write("# Token Details:\n")
                f.write(f'# Token Type: {tokens["token_type"]}\n')
                f.write(f'# Expires In: {tokens["expires_in"]} seconds\n')
                f.write(f'# Environment: {"Sandbox" if self.sandbox else "Production"}\n')
            
            print("💾 Tokens saved to qb_tokens.txt")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save tokens: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up resources"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            print("🧹 Callback server stopped")

def main():
    """Main OAuth flow"""
    print("🚀 QuickBooks OAuth 2.0 Helper")
    print("=" * 50)
    
    # Initialize OAuth helper
    oauth = QuickBooksOAuth()
    
    # Validate configuration
    if not oauth.validate_config():
        print("\n💡 Make sure your .env file contains:")
        print("   QB_CLIENT_ID=your_client_id")
        print("   QB_CLIENT_SECRET=your_client_secret")
        print("   QB_SANDBOX=True  # or False for production")
        return
    
    try:
        # Start callback server
        if not oauth.start_callback_server():
            return
        
        # Generate authorization URL
        auth_url = oauth.generate_auth_url()
        
        print("\n🔗 Opening QuickBooks authorization page...")
        print(f"   URL: {auth_url}")
        print("\n📋 Instructions:")
        print("   1. Your browser should open automatically")
        print("   2. If not, copy the URL above and open it manually")
        print("   3. Sign in to QuickBooks and authorize the app")
        print("   4. You'll be redirected back automatically")
        
        # Open browser
        try:
            webbrowser.open(auth_url)
        except:
            print("   ⚠️  Could not open browser automatically")
        
        # Wait for callback
        callback_data = oauth.wait_for_callback()
        
        if not callback_data:
            print("❌ Authorization failed or timed out")
            return
        
        print("✅ Authorization callback received!")
        
        # Exchange code for tokens
        tokens = oauth.exchange_code_for_tokens(
            callback_data['auth_code'], 
            callback_data['realm_id']
        )
        
        if not tokens:
            print("❌ Failed to get access tokens")
            return
        
        print("✅ Access tokens obtained!")
        print(f"   Access Token: {tokens['access_token'][:20]}...")
        print(f"   Company ID: {tokens['company_id']}")
        print(f"   Expires In: {tokens['expires_in']} seconds")
        
        # Test API connection
        if oauth.test_api_connection(tokens['access_token'], tokens['company_id']):
            # Save tokens
            oauth.save_tokens(tokens)
            
            print("\n🎉 Success! Your QuickBooks tokens are ready!")
            print("\n📓 Next steps:")
            print("   1. Open your Jupyter notebook")
            print("   2. Copy the tokens from qb_tokens.txt")
            print("   3. Paste them into the notebook's authentication cell")
            print("   4. Run the notebook to extract your data")
            
            print("\n📋 Copy these lines into your Jupyter notebook:")
            print(f'ACCESS_TOKEN = "{tokens["access_token"]}"')
            print(f'COMPANY_ID = "{tokens["company_id"]}"')
        
    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
    
    finally:
        # Cleanup
        oauth.cleanup()

if __name__ == "__main__":
    main() 