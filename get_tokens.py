#!/usr/bin/env python3
"""
QuickBooks Token Extractor

This script helps you get your access tokens from your Flask app
to use in the Jupyter notebook.

Usage:
1. Run your Flask app locally: python app.py
2. Go through the OAuth flow in your browser
3. Run this script to extract tokens from the session
"""

import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def get_tokens_from_flask_app(flask_url="http://localhost:5000"):
    """
    Try to get tokens from your running Flask app
    """
    print("🔍 Attempting to get tokens from Flask app...")
    print(f"   Flask URL: {flask_url}")
    
    try:
        # Try to get session info from Flask app
        response = requests.get(f"{flask_url}/api/session-info")
        
        if response.status_code == 200:
            session_data = response.json()
            
            access_token = session_data.get("access_token")
            company_id = session_data.get("company_id")
            
            if access_token and company_id:
                print("✅ Tokens found!")
                print(f"   Access Token: {access_token[:20]}...")
                print(f"   Company ID: {company_id}")
                
                # Save to a file for easy copying
                with open("tokens.txt", "w") as f:
                    f.write(f"ACCESS_TOKEN = \"{access_token}\"\n")
                    f.write(f"COMPANY_ID = \"{company_id}\"\n")
                
                print("💾 Tokens saved to tokens.txt")
                print("\n📋 Copy these lines into your Jupyter notebook:")
                print(f"ACCESS_TOKEN = \"{access_token}\"")
                print(f"COMPANY_ID = \"{company_id}\"")
                
                return access_token, company_id
            else:
                print("❌ No tokens found in session")
                return None, None
        else:
            print(f"❌ Flask app not responding: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ Error connecting to Flask app: {str(e)}")
        return None, None

def add_session_info_endpoint():
    """
    Instructions to add session info endpoint to your Flask app
    """
    print("\n📝 To use this script, add this endpoint to your app.py:")
    print("""
@app.route('/api/session-info')
def session_info():
    return jsonify({
        'access_token': session.get('access_token'),
        'company_id': session.get('company_id'),
        'authenticated': 'access_token' in session
    })
""")

def manual_token_entry():
    """
    Manual token entry if Flask method doesn't work
    """
    print("\n🔧 Manual Token Entry:")
    print("If you can't get tokens automatically, you can:")
    print("1. Check your Railway logs for access_token and company_id")
    print("2. Look in your browser's developer tools during OAuth")
    print("3. Add debug prints to your Flask app")
    
    access_token = input("\nEnter ACCESS_TOKEN (or press Enter to skip): ").strip()
    company_id = input("Enter COMPANY_ID (or press Enter to skip): ").strip()
    
    if access_token and company_id:
        with open("tokens.txt", "w") as f:
            f.write(f"ACCESS_TOKEN = \"{access_token}\"\n")
            f.write(f"COMPANY_ID = \"{company_id}\"\n")
        
        print("✅ Tokens saved to tokens.txt")
        return access_token, company_id
    else:
        print("⚠️  No tokens entered")
        return None, None

def main():
    print("🚀 QuickBooks Token Extractor")
    print("=" * 50)
    
    # Method 1: Try to get from Flask app
    access_token, company_id = get_tokens_from_flask_app()
    
    if not (access_token and company_id):
        print("\n🔄 Trying Railway URL...")
        railway_url = "https://web-production-33315.up.railway.app"
        access_token, company_id = get_tokens_from_flask_app(railway_url)
    
    if not (access_token and company_id):
        # Method 2: Show instructions for adding endpoint
        add_session_info_endpoint()
        
        # Method 3: Manual entry
        access_token, company_id = manual_token_entry()
    
    if access_token and company_id:
        print("\n🎉 Success! You can now use these tokens in your Jupyter notebook.")
        print("📓 Open quickbooks_api_notebook.ipynb and paste the tokens in cell 4.")
    else:
        print("\n⚠️  No tokens obtained. You'll need to use the OAuth flow in the notebook.")

if __name__ == "__main__":
    main() 