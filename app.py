from flask import Flask, render_template, redirect, url_for, session, request, flash, jsonify
import os
from dotenv import load_dotenv
import requests
import uuid
import json
from urllib.parse import quote_plus
import base64
import threading
import subprocess
import sys
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key-change-this-in-production')

# QuickBooks API Configuration
QB_CLIENT_ID = os.getenv('QB_CLIENT_ID')
QB_CLIENT_SECRET = os.getenv('QB_CLIENT_SECRET')
QB_SANDBOX = os.getenv('QB_SANDBOX', 'False').lower() == 'true'

# Auto-detect environment and set appropriate redirect URI
def get_redirect_uri():
    """Get the appropriate redirect URI based on environment"""
    # Check if we have a custom redirect URI set
    custom_uri = os.getenv('QB_REDIRECT_URI')
    if custom_uri:
        return custom_uri
    
    # Auto-detect based on common environment indicators
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'):
        # Production/Railway environment
        railway_domain = os.getenv('RAILWAY_STATIC_URL', 'your-app.railway.app')
        return f"https://{railway_domain}/callback"
    else:
        # Local development
        return "http://localhost:5000/callback"

QB_REDIRECT_URI = get_redirect_uri()

# QuickBooks API Endpoints
if QB_SANDBOX:
    QB_OAUTH_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"
else:
    QB_OAUTH_AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_BASE_URL = "https://quickbooks.api.intuit.com/v3/company"

# Jupyter Configuration
JUPYTER_PORT = int(os.getenv('JUPYTER_PORT', '8888'))
JUPYTER_PASSWORD = os.getenv('JUPYTER_PASSWORD', 'quickbooks123')
jupyter_process = None
jupyter_running = False

def setup_jupyter_config():
    """Set up Jupyter configuration for integrated deployment"""
    config_dir = os.path.expanduser('~/.jupyter')
    os.makedirs(config_dir, exist_ok=True)
    
    # Use token-based authentication instead of password
    jupyter_token = JUPYTER_PASSWORD  # Use the password as a token for simplicity
    
    config_content = f"""
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = {JUPYTER_PORT}
c.ServerApp.open_browser = False
c.ServerApp.token = '{jupyter_token}'
c.ServerApp.password = ''
c.ServerApp.allow_root = True
c.ServerApp.allow_origin = '*'
c.ServerApp.disable_check_xsrf = True
c.ServerApp.notebook_dir = '{os.getcwd()}'
c.ServerApp.allow_remote_access = True
"""
    
    config_path = os.path.join(config_dir, 'jupyter_server_config.py')
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    return config_path

def start_jupyter_server():
    """Start Jupyter server in background thread"""
    global jupyter_process, jupyter_running
    
    if jupyter_running:
        print("ℹ️  Jupyter is already running")
        return True
    
    try:
        # First check if jupyter is available
        print("🔍 Checking if Jupyter is available...")
        check_cmd = [sys.executable, '-m', 'jupyter', '--version']
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        
        if check_result.returncode != 0:
            error_msg = f"Jupyter not available: {check_result.stderr}"
            print(f"❌ {error_msg}")
            return False
        
        print(f"✅ Jupyter found: {check_result.stdout.strip()}")
        
        # Set up configuration
        config_path = setup_jupyter_config()
        print(f"✅ Config created: {config_path}")
        
        cmd = [
            sys.executable, '-m', 'jupyter', 'lab',
            '--config', config_path,
            '--no-browser',
            '--allow-root'
        ]
        
        print(f"🚀 Starting Jupyter Lab on port {JUPYTER_PORT}...")
        print(f"   Command: {' '.join(cmd)}")
        
        jupyter_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give Jupyter a moment to start
        print("⏳ Waiting for Jupyter to start...")
        time.sleep(5)
        
        if jupyter_process.poll() is None:
            jupyter_running = True
            print(f"✅ Jupyter Lab started successfully on port {JUPYTER_PORT}")
            print(f"   Process ID: {jupyter_process.pid}")
            return True
        else:
            # Get error output
            stdout, stderr = jupyter_process.communicate()
            print("❌ Failed to start Jupyter Lab")
            print(f"   Exit code: {jupyter_process.returncode}")
            if stdout:
                print(f"   Stdout: {stdout}")
            if stderr:
                print(f"   Stderr: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Jupyter version check timed out")
        return False
    except Exception as e:
        print(f"❌ Error starting Jupyter: {str(e)}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def stop_jupyter_server():
    """Stop Jupyter server"""
    global jupyter_process, jupyter_running
    
    if jupyter_process and jupyter_running:
        jupyter_process.terminate()
        jupyter_process.wait()
        jupyter_running = False
        print("🛑 Jupyter Lab stopped")

def is_jupyter_running():
    """Check if Jupyter server is running"""
    global jupyter_process, jupyter_running
    
    if not jupyter_running or not jupyter_process:
        return False
    
    return jupyter_process.poll() is None

@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DataRift - QuickBooks Integration</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .hero-section {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 100px 0;
            }
            .feature-card {
                transition: transform 0.3s ease;
                border: none;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .feature-card:hover {
                transform: translateY(-5px);
            }
        </style>
    </head>
    <body>
        <div class="hero-section text-center">
            <div class="container">
                <h1 class="display-4 fw-bold mb-4">DataRift</h1>
                <p class="lead mb-5">Connect to QuickBooks and analyze your business data in real-time</p>
                <a href="/auth" class="btn btn-light btn-lg px-5">Connect to QuickBooks</a>
            </div>
        </div>
        <div class="container my-5">
            <div class="row">
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">Real-time Data</h5>
                            <p class="card-text">Get live data from your QuickBooks account</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">Easy Analysis</h5>
                            <p class="card-text">Analyze your business data with powerful tools</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4 mb-4">
                    <div class="card feature-card h-100">
                        <div class="card-body text-center">
                            <h5 class="card-title">Export Data</h5>
                            <p class="card-text">Export your data in various formats</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-4">
                <div class="col-md-12 text-center">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">🪐 Jupyter Notebook Analysis</h5>
                            <p class="card-text">Get your QuickBooks tokens and use them in a local Jupyter notebook for advanced data analysis</p>
                            <div class="d-grid gap-2 d-md-flex justify-content-md-center">
                                <a href="/tokens" class="btn btn-success btn-lg">Get Tokens for Local Jupyter</a>
                                <a href="/config" class="btn btn-outline-info">Check OAuth Config</a>
                                <a href="/jupyter" class="btn btn-outline-secondary">Integrated Jupyter (Advanced)</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

@app.route("/auth")
def auth():
    state = str(uuid.uuid4())
    session["oauth_state"] = state
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

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    realm_id = request.args.get("realmId")

    if not code or not state:
        return "Missing authorization code or state", 400

    if state != session.get("oauth_state"):
        return "Invalid state parameter", 400

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": QB_REDIRECT_URI
    }

    auth_string = f"{QB_CLIENT_ID}:{QB_CLIENT_SECRET}"
    auth_header = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(QB_OAUTH_TOKEN_URL, data=token_data, headers=headers)
    
    if response.status_code == 200:
        token_response = response.json()
        session["access_token"] = token_response["access_token"]
        session["refresh_token"] = token_response["refresh_token"]
        session["company_id"] = realm_id
        session["expires_in"] = token_response["expires_in"]
        session["x_refresh_token_expires_in"] = token_response["x_refresh_token_expires_in"]
        return redirect("/dashboard")
    else:
        return f"Token exchange failed: {response.status_code} - {response.text}", 400

@app.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        flash("Please connect to QuickBooks first.", "warning")
        return redirect("/")
    
    return render_template("dashboard.html")

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
        print(f"Making QB query: {query}")
        print(f"URL: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(f"Response status: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making QB request: {response.status_code} - {response.text}")
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

@app.route("/api/classes")
def get_classes():
    data = make_quickbooks_api_call("SELECT * FROM Class")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get("QueryResponse", {}).get("Class", []))
# Transaction Data Endpoints
@app.route('/api/journal_entries')
def get_journal_entries():
    data = make_quickbooks_api_call("SELECT * FROM JournalEntry")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('JournalEntry', []))

@app.route('/api/deposits')
def get_deposits():
    data = make_quickbooks_api_call("SELECT * FROM Deposit")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Deposit', []))

@app.route('/api/expenses')
def get_expenses():
    data = make_quickbooks_api_call("SELECT * FROM Purchase")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Purchase', []))

@app.route('/api/transfers')
def get_transfers():
    data = make_quickbooks_api_call("SELECT * FROM Transfer")
    if isinstance(data, tuple):
        return jsonify(data[0]), data[1]
    return jsonify(data.get('QueryResponse', {}).get('Transfer', []))

@app.route('/api/sync')
def sync_data():
    # Get counts safely
    customer_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Customer")
    invoice_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Invoice")
    item_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Item")
    payment_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Payment")
    journal_result = make_quickbooks_api_call("SELECT COUNT(*) FROM JournalEntry")
    deposit_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Deposit")
    expense_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Purchase")
    transfer_result = make_quickbooks_api_call("SELECT COUNT(*) FROM Transfer")
    
    # Handle errors safely
    def safe_get_count(result):
        if isinstance(result, tuple):
            return 0  # Return 0 if there's an error
        return result.get('QueryResponse', {}).get('totalCount', 0)
    
    return jsonify({
        "message": "Data sync initiated",
        "counts": {
            "customers": safe_get_count(customer_result),
            "invoices": safe_get_count(invoice_result),
            "items": safe_get_count(item_result),
            "payments": safe_get_count(payment_result),
            "journal_entries": safe_get_count(journal_result),
            "deposits": safe_get_count(deposit_result),
            "expenses": safe_get_count(expense_result),
            "transfers": safe_get_count(transfer_result)
        },
        "status": "success"
    })
    
@app.route("/new_dashboard")
def new_dashboard():
    # Get counts safely
    customer_result = make_quickbooks_api_call("SELECT * FROM Customer")
    invoice_result = make_quickbooks_api_call("SELECT * FROM Invoice")
    item_result = make_quickbooks_api_call("SELECT * FROM Item")
    payment_result = make_quickbooks_api_call("SELECT * FROM Payment")
    journal_result = make_quickbooks_api_call("SELECT * FROM JournalEntry")
    deposit_result = make_quickbooks_api_call("SELECT * FROM Deposit")
    expense_result = make_quickbooks_api_call("SELECT * FROM Purchase")
    transfer_result = make_quickbooks_api_call("SELECT * FROM Transfer")


    return render_template("new_dashboard.html",
       customer_data=customer_result.get("QueryResponse", {}).get("Customer", []),
        invoice_data=invoice_result.get("QueryResponse", {}).get("Invoice", []),
        item_data=item_result.get("QueryResponse", {}).get("Item", []),
        payment_data=payment_result.get("QueryResponse", {}).get("Payment", []),
        journal_data=journal_result.get("QueryResponse", {}).get("JournalEntry", []),
        deposit_data=deposit_result.get("QueryResponse", {}).get("Deposit", []),
        expense_data=expense_result.get("QueryResponse", {}).get("Purchase", []),
        transfer_data=transfer_result.get("QueryResponse", {}).get("Transfer", [])
        )

# QBO-Style Transaction Endpoint
@app.route("/api/transactions/qbo-style")
def get_transactions_qbo_style():
    """Get all transactions formatted like QBO export"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    from datetime import datetime
    
    unified_transactions = []
    
    # Helper function to convert QB data to QBO export format
    def convert_to_qbo_format(transaction, transaction_type):
        """Convert QuickBooks transaction to QBO export format"""
        
        # Base QBO export structure
        qbo_row = {
            "Transaction date": "",
            "Distribution account": "",
            "Name": "",
            "Transaction type": "",
            "Transaction type_2": "",  # Duplicate column as in QBO
            "Memo/Description": "",
            "Item split account full name": "",
            "Amount": 0,
            "Customer": "",
            "Full name": "",
            "Supplier": "",
            "Distribution account type": "",
            "Item class": "",
            "Class full name": ""
        }
        
        # Set transaction date
        qbo_row["Transaction date"] = transaction.get("TxnDate", "")
        
        # Set transaction type
        qbo_row["Transaction type"] = transaction_type
        qbo_row["Transaction type_2"] = transaction_type
        
        # Extract amount and set as negative for expenses
        amount = 0
        if transaction_type in ["Bill", "Bill Payment (Cheque)", "Expense"]:
            amount = -abs(float(transaction.get("TotalAmt", 0)))
        else:
            amount = float(transaction.get("TotalAmt", 0))
        
        qbo_row["Amount"] = amount
        
        # Set basic info
        qbo_row["Name"] = transaction.get("DocNumber", transaction_type)
        qbo_row["Memo/Description"] = transaction.get("PrivateNote", transaction.get("DocNumber", ""))
        
        # Process based on transaction type
        if transaction_type == "Journal Entry":
            qbo_row["Distribution account"] = "Other"
            qbo_row["Distribution account type"] = "Other"
            
            # Process journal entry lines for better account info
            for line in transaction.get("Line", []):
                if line.get("DetailType") == "JournalEntryLineDetail":
                    detail = line.get("JournalEntryLineDetail", {})
                    account = detail.get("AccountRef", {})
                    if account.get("name"):
                        qbo_row["Distribution account"] = account.get("name", "")
                        qbo_row["Item split account full name"] = account.get("name", "")
                        break
                        
        elif transaction_type == "Deposit":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
            # Get deposit account
            deposit_account = transaction.get("DepositToAccountRef", {})
            if deposit_account.get("name"):
                qbo_row["Distribution account"] = deposit_account.get("name", "")
                qbo_row["Item split account full name"] = deposit_account.get("name", "")
                
        elif transaction_type == "Bill":
            qbo_row["Distribution account"] = "Accounts Payable"
            qbo_row["Distribution account type"] = "Accounts payable (A/P)"
            
            # Get vendor info
            vendor_ref = transaction.get("VendorRef", {})
            qbo_row["Supplier"] = vendor_ref.get("name", "")
            qbo_row["Full name"] = vendor_ref.get("name", "")
            
        elif transaction_type == "Transfer":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
        elif transaction_type == "Payment":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
            
        elif transaction_type == "Invoice":
            qbo_row["Distribution account"] = "Accounts Receivable"
            qbo_row["Distribution account type"] = "Accounts receivable (A/R)"
            
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
        
        elif transaction_type == "Bill Payment":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
            # Get vendor info
            vendor_ref = transaction.get("VendorRef", {})
            qbo_row["Supplier"] = vendor_ref.get("name", "")
            qbo_row["Full name"] = vendor_ref.get("name", "")
            
        elif transaction_type == "Expense":
            qbo_row["Distribution account"] = "Expense Account"
            qbo_row["Distribution account type"] = "Expense"
            
            # Get vendor info
            vendor_ref = transaction.get("VendorRef", {})
            qbo_row["Supplier"] = vendor_ref.get("name", "")
            qbo_row["Full name"] = vendor_ref.get("name", "")
            
        elif transaction_type == "Refund Receipt":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
            
        elif transaction_type == "Credit Memo":
            qbo_row["Distribution account"] = "Accounts Receivable"
            qbo_row["Distribution account type"] = "Accounts receivable (A/R)"
            
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
            
        elif transaction_type == "Sales Receipt":
            qbo_row["Distribution account"] = "Bank Account"
            qbo_row["Distribution account type"] = "Bank"
            
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
            qbo_row["Distribution account"] = "Accounts Receivable"
            qbo_row["Distribution account type"] = "Accounts receivable (A/R)"
                
            # Get customer info
            customer_ref = transaction.get("CustomerRef", {})
            qbo_row["Customer"] = customer_ref.get("name", "")
            qbo_row["Full name"] = customer_ref.get("name", "")
            
            return qbo_row    # Convert to pandas DataFrame
    df = pd.DataFrame(unified_transactions)
    
    if df.empty:
        return jsonify({
            "transactions": [],
            "total_count": 0,
            "summary": {},
            "qbo_format": True
        })
    
    # Convert date column to datetime and sort
    df["Transaction date"] = pd.to_datetime(df["Transaction date"], errors="coerce")
    df = df.sort_values("Transaction date", ascending=False)
    
    # Format date back to string for JSON
    df["Transaction date"] = df["Transaction date"].dt.strftime("%Y/%m/%d")
    
    # Create summary statistics
    summary = {
        "by_type": df["Transaction type"].value_counts().to_dict(),
        "total_amount": df["Amount"].sum(),
        "average_amount": df["Amount"].mean(),
        "date_range": {
            "earliest": df["Transaction date"].min() if not df["Transaction date"].isna().all() else "N/A",
            "latest": df["Transaction date"].max() if not df["Transaction date"].isna().all() else "N/A"
        },
        "amount_by_type": df.groupby("Transaction type")["Amount"].sum().to_dict()
    }
    
    # Convert DataFrame back to list of dictionaries for JSON response
    transactions_list = df.fillna("").to_dict("records")
    
    return jsonify({
        "transactions": transactions_list,
        "total_count": len(transactions_list),
        "summary": summary,
        "qbo_format": True,
        "columns": list(df.columns)
    })

# QBO-Style CSV Export
@app.route("/api/transactions/export/qbo-style")
def export_transactions_qbo_style():
    """Export transactions in QBO export format"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    from flask import Response
    
    # Get the QBO-style transaction data
    transactions_data = get_transactions_qbo_style()
    if isinstance(transactions_data, tuple):
        return transactions_data
    
    transactions = transactions_data.get_json()["transactions"]
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if df.empty:
        return Response("No data available", mimetype="text/csv")
    
    # Create CSV content with QBO-style formatting
    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8")
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=quickbooks_transactions_qbo_style.csv"}
    )

# Enhanced Pandas-based Transaction Endpoint
@app.route('/api/transactions/pandas')
def get_transactions_pandas():
    """Get all transactions using pandas for better data processing"""
    if 'access_token' not in session or 'company_id' not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    from datetime import datetime
    
    unified_transactions = []
    
    # Helper function to standardize transaction data
    def standardize_transaction(transaction, transaction_type):
        """Convert different transaction types to a common format"""
        base_data = {
            'id': transaction.get('Id', ''),
            'type': transaction_type,
            'date': transaction.get('TxnDate', ''),
            'amount': 0,
            'description': '',
            'reference': transaction.get('DocNumber', ''),
            'status': 'Unknown',
            'created_time': transaction.get('MetaData', {}).get('CreateTime', ''),
            'last_modified': transaction.get('MetaData', {}).get('LastUpdatedTime', '')
        }
        
        # Extract amount based on transaction type
        if transaction_type == 'JournalEntry':
            # Sum up all line amounts
            total_amount = 0
            for line in transaction.get('Line', []):
                if 'Amount' in line:
                    total_amount += float(line['Amount'])
            base_data['amount'] = total_amount
            base_data['description'] = transaction.get('DocNumber', 'Journal Entry')
            
        elif transaction_type == 'Deposit':
            base_data['amount'] = float(transaction.get('TotalAmt', 0))
            base_data['description'] = f"Deposit - {transaction.get('DocNumber', 'No Ref')}"
            base_data['status'] = 'Completed'
            
        elif transaction_type == 'Purchase':
            base_data['amount'] = float(transaction.get('TotalAmt', 0))
            base_data['description'] = f"Expense - {transaction.get('DocNumber', 'No Ref')}"
            base_data['status'] = 'Completed'
            
        elif transaction_type == 'Transfer':
            base_data['amount'] = float(transaction.get('Amount', 0))
            base_data['description'] = f"Transfer - {transaction.get('DocNumber', 'No Ref')}"
            base_data['status'] = 'Completed'
            
        elif transaction_type == 'Payment':
            base_data['amount'] = float(transaction.get('TotalAmt', 0))
            base_data['description'] = f"Payment - {transaction.get('DocNumber', 'No Ref')}"
            base_data['status'] = 'Completed'
            
        elif transaction_type == 'Invoice':
            base_data['amount'] = float(transaction.get('TotalAmt', 0))
            base_data['description'] = f"Invoice - {transaction.get('DocNumber', 'No Ref')}"
            base_data['status'] = transaction.get('EmailStatus', 'Unknown')
            
        return base_data
    
    # Fetch all transaction types
    transaction_types = [
        ("JournalEntry", "Journal Entry"),
        ("Deposit", "Deposit"),
        ("Purchase", "Bill"),
        ("Transfer", "Transfer"),
        ("Payment", "Payment"),
        ("Invoice", "Invoice"),
        ("Bill", "Bill"),
        ("BillPayment", "Bill Payment"),
        ("Expense", "Expense"),
        ("RefundReceipt", "Refund Receipt"),
        ("CreditMemo", "Credit Memo"),
        ("SalesReceipt", "Sales Receipt"),
        ('JournalEntry', 'Journal Entries'),
        ('Deposit', 'Deposits'),
        ('Purchase', 'Expenses'),
        ('Transfer', 'Transfers'),
        ('Payment', 'Payments'),
        ('Invoice', 'Invoices')
    ]
    
    for entity_type, display_name in transaction_types:
        try:
            result = make_quickbooks_api_call(f"SELECT * FROM {entity_type}")
            
            if isinstance(result, tuple):
                print(f"Error fetching {display_name}: {result[0]}")
                continue
                
            transactions = result.get('QueryResponse', {}).get(entity_type, [])
            
            for transaction in transactions:
                standardized = standardize_transaction(transaction, entity_type)
                unified_transactions.append(standardized)
                
        except Exception as e:
            print(f"Error processing {display_name}: {str(e)}")
            continue
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(unified_transactions)
    
    if df.empty:
        return jsonify({
            'transactions': [],
            'total_count': 0,
            'summary': {},
            'pandas_info': 'No data available'
        })
    
    # Convert date columns to datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
    df['last_modified'] = pd.to_datetime(df['last_modified'], errors='coerce')
    
    # Sort by date (most recent first)
    df = df.sort_values('date', ascending=False)
    
    # Create summary statistics
    summary = {
        'by_type': df['type'].value_counts().to_dict(),
        'total_amount': df['amount'].sum(),
        'average_amount': df['amount'].mean(),
        'date_range': {
            'earliest': df['date'].min().strftime('%Y-%m-%d') if not df['date'].isna().all() else 'N/A',
            'latest': df['date'].max().strftime('%Y-%m-%d') if not df['date'].isna().all() else 'N/A'
        },
        'amount_by_type': df.groupby('type')['amount'].sum().to_dict()
    }
    
    # Convert DataFrame back to list of dictionaries for JSON response
    transactions_list = df.fillna('').to_dict('records')
    
    return jsonify({
        'transactions': transactions_list,
        'total_count': len(transactions_list),
        'summary': summary,
        'pandas_info': {
            'shape': df.shape,
            'columns': list(df.columns),
            'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
        }
    })

# Enhanced CSV Export with Pandas
@app.route('/api/transactions/export/pandas')
def export_transactions_pandas_csv():
    """Export all transactions as CSV using pandas"""
    if 'access_token' not in session or 'company_id' not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    from flask import Response
    
    # Get the unified transaction data
    transactions_data = get_transactions_pandas()
    if isinstance(transactions_data, tuple):
        return transactions_data
    
    transactions = transactions_data.get_json()['transactions']
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if df.empty:
        return Response("No data available", mimetype='text/csv')
    
    # Convert date columns
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
    df['last_modified'] = pd.to_datetime(df['last_modified'], errors='coerce')
    
    # Format dates for CSV
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    df['created_time'] = df['created_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['last_modified'] = df['last_modified'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Create CSV content
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8')
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=quickbooks_transactions_pandas.csv'}
    )

# Excel Export with Pandas
@app.route('/api/transactions/export/excel')

@app.route("/api/transactions/raw")

@app.route("/raw-data")
def raw_data_page():
    """Display raw transaction data page"""
    if "access_token" not in session or "company_id" not in session:
        flash("Please connect to QuickBooks first.", "warning")
        return redirect("/")
    
    return render_template("raw_data.html")

def get_raw_transactions():
    """Get all raw transaction data in one giant table"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    from datetime import datetime
    
    all_transactions = []
    
    # Define all transaction types to fetch
    transaction_types = [
        ("JournalEntry", "Journal Entry"),
        ("Deposit", "Deposit"),
        ("Purchase", "Bill"),
        ("Transfer", "Transfer"),
        ("Payment", "Payment"),
        ("Invoice", "Invoice"),
        ("Bill", "Bill"),
        ("BillPayment", "Bill Payment"),
        ("Expense", "Expense"),
        ("RefundReceipt", "Refund Receipt"),
        ("CreditMemo", "Credit Memo"),
        ("SalesReceipt", "Sales Receipt"),
        ("JournalEntry", "Journal Entry"),
        ("Deposit", "Deposit"),
        ("Purchase", "Purchase"),
        ("Transfer", "Transfer"),
        ("Payment", "Payment"),
        ("Invoice", "Invoice"),
        ("Bill", "Bill"),
        ("BillPayment", "Bill Payment"),
        ("Expense", "Expense"),
        ("RefundReceipt", "Refund Receipt"),
        ("CreditMemo", "Credit Memo"),
        ("SalesReceipt", "Sales Receipt")
    ]
    
    for entity_type, display_name in transaction_types:
        try:
            print(f"Fetching {display_name} transactions...")
            result = make_quickbooks_api_call(f"SELECT * FROM {entity_type}")
            
            if isinstance(result, tuple):
                print(f"Error fetching {display_name}: {result[0]}")
                continue
                
            transactions = result.get("QueryResponse", {}).get(entity_type, [])
            
            for transaction in transactions:
                # Flatten the transaction data
                flat_transaction = {
                    "Transaction_Type": display_name,
                    "ID": transaction.get("Id", ""),
                    "SyncToken": transaction.get("SyncToken", ""),
                    "MetaData_CreateTime": transaction.get("MetaData", {}).get("CreateTime", ""),
                    "MetaData_LastUpdatedTime": transaction.get("MetaData", {}).get("LastUpdatedTime", ""),
                    "DocNumber": transaction.get("DocNumber", ""),
                    "TxnDate": transaction.get("TxnDate", ""),
                    "TotalAmt": transaction.get("TotalAmt", 0),
                    "CurrencyRef": transaction.get("CurrencyRef", {}).get("value", ""),
                    "PrivateNote": transaction.get("PrivateNote", ""),
                    "LineCount": transaction.get("LineCount", 0)
                }
                
                # Add customer info if available
                if "CustomerRef" in transaction:
                    flat_transaction["Customer_ID"] = transaction["CustomerRef"].get("value", "")
                    flat_transaction["Customer_Name"] = transaction["CustomerRef"].get("name", "")
                else:
                    flat_transaction["Customer_ID"] = ""
                    flat_transaction["Customer_Name"] = ""
                
                # Add vendor info if available
                if "VendorRef" in transaction:
                    flat_transaction["Vendor_ID"] = transaction["VendorRef"].get("value", "")
                    flat_transaction["Vendor_Name"] = transaction["VendorRef"].get("name", "")
                else:
                    flat_transaction["Vendor_ID"] = ""
                    flat_transaction["Vendor_Name"] = ""
                
                # Add account info if available
                if "DepositToAccountRef" in transaction:
                    flat_transaction["DepositToAccount_ID"] = transaction["DepositToAccountRef"].get("value", "")
                    flat_transaction["DepositToAccount_Name"] = transaction["DepositToAccountRef"].get("name", "")
                else:
                    flat_transaction["DepositToAccount_ID"] = ""
                    flat_transaction["DepositToAccount_Name"] = ""
                
                # Add payment method if available
                if "PaymentMethodRef" in transaction:
                    flat_transaction["PaymentMethod_ID"] = transaction["PaymentMethodRef"].get("value", "")
                    flat_transaction["PaymentMethod_Name"] = transaction["PaymentMethodRef"].get("name", "")
                else:
                    flat_transaction["PaymentMethod_ID"] = ""
                    flat_transaction["PaymentMethod_Name"] = ""
                
                # Add line items details
                if "Line" in transaction and transaction["Line"]:
                    line_items = []
                    for line in transaction["Line"]:
                        line_detail = {
                            "LineId": line.get("Id", ""),
                            "LineNum": line.get("LineNum", ""),
                            "Description": line.get("Description", ""),
                            "Amount": line.get("Amount", 0),
                            "DetailType": line.get("DetailType", "")
                        }
                        
                        # Add account info for line items
                        if "AccountBasedExpenseLineDetail" in line:
                            account_detail = line["AccountBasedExpenseLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                            # Add Class info from expense line detail
                            if "ClassRef" in account_detail:
                                line_detail["Class_ID"] = account_detail.get("ClassRef", {}).get("value", "")
                                line_detail["Class_Name"] = account_detail.get("ClassRef", {}).get("name", "")
                            else:
                                line_detail["Class_ID"] = ""
                                line_detail["Class_Name"] = ""
                        if "JournalEntryLineDetail" in line:
                            account_detail = line["JournalEntryLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                            # Add Class info from journal entry line detail
                            if "ClassRef" in account_detail:
                                line_detail["Class_ID"] = account_detail.get("ClassRef", {}).get("value", "")
                                line_detail["Class_Name"] = account_detail.get("ClassRef", {}).get("name", "")
                            else:
                                line_detail["Class_ID"] = ""
                                line_detail["Class_Name"] = ""
                        elif "DepositLineDetail" in line:
                            account_detail = line["DepositLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                            # Add Class info from deposit line detail
                            if "ClassRef" in account_detail:
                                line_detail["Class_ID"] = account_detail.get("ClassRef", {}).get("value", "")
                                line_detail["Class_Name"] = account_detail.get("ClassRef", {}).get("name", "")
                            else:
                                line_detail["Class_ID"] = ""
                                line_detail["Class_Name"] = ""
                        elif "SalesItemLineDetail" in line:
                            account_detail = line["SalesItemLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                            # Add Class info from sales item line detail
                            if "ClassRef" in account_detail:
                                line_detail["Class_ID"] = account_detail.get("ClassRef", {}).get("value", "")
                                line_detail["Class_Name"] = account_detail.get("ClassRef", {}).get("name", "")
                            else:
                                line_detail["Class_ID"] = ""
                                line_detail["Class_Name"] = ""
                        elif "ItemBasedExpenseLineDetail" in line:
                            account_detail = line["ItemBasedExpenseLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                            # Add Class info from item based expense line detail
                            if "ClassRef" in account_detail:
                                line_detail["Class_ID"] = account_detail.get("ClassRef", {}).get("value", "")
                                line_detail["Class_Name"] = account_detail.get("ClassRef", {}).get("name", "")
                            else:
                                line_detail["Class_ID"] = ""
                                line_detail["Class_Name"] = ""
                        else:
                            line_detail["Account_ID"] = ""
                            line_detail["Account_Name"] = ""
                            line_detail["Class_ID"] = ""
                            line_detail["Class_Name"] = ""
                        if "JournalEntryLineDetail" in line:
                            account_detail = line["JournalEntryLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                        elif "DepositLineDetail" in line:
                            account_detail = line["DepositLineDetail"]
                            line_detail["Account_ID"] = account_detail.get("AccountRef", {}).get("value", "")
                            line_detail["Account_Name"] = account_detail.get("AccountRef", {}).get("name", "")
                        else:
                            line_detail["Account_ID"] = ""
                            line_detail["Account_Name"] = ""
                        
                        line_items.append(line_detail)
                    
                    flat_transaction["Line_Items"] = line_items
                    flat_transaction["Line_Items_Count"] = len(line_items)
                else:
                    flat_transaction["Line_Items"] = []
                    flat_transaction["Line_Items_Count"] = 0
                
                # Add raw JSON for complete data
                flat_transaction["Raw_JSON"] = str(transaction)
                
                all_transactions.append(flat_transaction)
                
        except Exception as e:
            print(f"Error processing {display_name}: {str(e)}")
            continue
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(all_transactions)
    
    if df.empty:
        return jsonify({
            "transactions": [],
            "total_count": 0,
            "summary": {},
            "raw_format": True
        })
    
    # Sort by date (most recent first)
    df["TxnDate"] = pd.to_datetime(df["TxnDate"], errors="coerce")
    df = df.sort_values("TxnDate", ascending=False)
    
    # Format date back to string for JSON
    df["TxnDate"] = df["TxnDate"].dt.strftime("%Y-%m-%d")
    
    # Create summary statistics
    summary = {
        "by_type": df["Transaction_Type"].value_counts().to_dict(),
        "total_amount": df["TotalAmt"].sum(),
        "average_amount": df["TotalAmt"].mean(),
        "date_range": {
            "earliest": df["TxnDate"].min() if not df["TxnDate"].isna().all() else "N/A",
            "latest": df["TxnDate"].max() if not df["TxnDate"].isna().all() else "N/A"
        },
        "amount_by_type": df.groupby("Transaction_Type")["TotalAmt"].sum().to_dict(),
        "total_transactions": len(df),
        "unique_customers": df["Customer_Name"].nunique(),
        "unique_vendors": df["Vendor_Name"].nunique()
    }
    
    # Convert DataFrame back to list of dictionaries for JSON response
    transactions_list = df.fillna("").to_dict("records")
    
    return jsonify({
        "transactions": transactions_list,
        "total_count": len(transactions_list),
        "summary": summary,
        "raw_format": True,
        "columns": list(df.columns)
    })

def export_transactions_excel():
    """Export all transactions as Excel file using pandas"""
    if 'access_token' not in session or 'company_id' not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    from flask import Response
    
    # Get the unified transaction data
    transactions_data = get_transactions_pandas()
    if isinstance(transactions_data, tuple):
        return transactions_data
    
    transactions = transactions_data.get_json()['transactions']
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if df.empty:
        return Response("No data available", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    # Convert date columns
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
    df['last_modified'] = pd.to_datetime(df['last_modified'], errors='coerce')
    
    # Create Excel content
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main transactions sheet
        df.to_excel(writer, sheet_name='Transactions', index=False)
        
        # Summary sheet
        summary_df = pd.DataFrame([
            ['Total Transactions', len(df)],
            ['Total Amount', f"${df['amount'].sum():.2f}"],
            ['Average Amount', f"${df['amount'].mean():.2f}"],
            ['Date Range', f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}"]
        ], columns=['Metric', 'Value'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # By type summary
        type_summary = df.groupby('type').agg({
            'amount': ['count', 'sum', 'mean']
        }).round(2)
        type_summary.columns = ['Count', 'Total Amount', 'Average Amount']
        type_summary.to_excel(writer, sheet_name='By Type')
    
    output.seek(0)
    excel_content = output.getvalue()
    output.close()
    
    return Response(
        excel_content,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=quickbooks_transactions.xlsx'}
    )

def show_tokens():
    return {
        'access_token': session.get('access_token'),
        'refresh_token': session.get('refresh_token'),
        'company_id': session.get('company_id'),
        'expires_in': session.get('expires_in'),
        'x_refresh_token_expires_in': session.get('x_refresh_token_expires_in')
    }

@app.route("/config")
def show_config():
    """Show current OAuth configuration for debugging"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OAuth Configuration - DataRift</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/">DataRift</a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/">Home</a>
                    <a class="nav-link" href="/dashboard">Dashboard</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h3 class="mb-0">🔧 OAuth Configuration</h3>
                        </div>
                        <div class="card-body">
                            <h5>Current Settings:</h5>
                            <ul class="list-group list-group-flush">
                                <li class="list-group-item"><strong>Client ID:</strong> {QB_CLIENT_ID[:10] + '...' if QB_CLIENT_ID else 'Not set'}</li>
                                <li class="list-group-item"><strong>Redirect URI:</strong> <code>{QB_REDIRECT_URI}</code></li>
                                <li class="list-group-item"><strong>Environment:</strong> {'🧪 Sandbox' if QB_SANDBOX else '🚀 Production'}</li>
                                <li class="list-group-item"><strong>Detected Environment:</strong> {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}</li>
                            </ul>
                            
                            <div class="alert alert-info mt-4">
                                <h6>📋 QuickBooks App Configuration Required:</h6>
                                <p>You need to add this redirect URI to your QuickBooks app:</p>
                                <ol>
                                    <li>Go to <a href="https://developer.intuit.com" target="_blank">QuickBooks Developer Dashboard</a></li>
                                    <li>Select your app</li>
                                    <li>Go to "Keys & OAuth"</li>
                                    <li>Add this redirect URI: <strong><code>{QB_REDIRECT_URI}</code></strong></li>
                                    <li>Save the changes</li>
                                </ol>
                            </div>
                            
                            <div class="alert alert-success mt-3">
                                <h6>✅ After adding the redirect URI:</h6>
                                <p>You can use the OAuth flow by visiting <a href="/auth">/auth</a></p>
                            </div>
                            
                            <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                <a href="/auth" class="btn btn-success">Test OAuth Flow</a>
                                <a href="/" class="btn btn-secondary">← Back to Home</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/railway-guide")
def railway_guide():
    """Display Railway token access guide"""
    try:
        with open('RAILWAY_TOKEN_ACCESS.md', 'r') as f:
            content = f.read()
        
        # Convert markdown to HTML (basic conversion)
        html_content = content.replace('\n# ', '\n<h1>').replace('\n## ', '\n<h2>').replace('\n### ', '\n<h3>')
        html_content = html_content.replace('\n**', '\n<strong>').replace('**', '</strong>')
        html_content = html_content.replace('\n- ', '\n<li>').replace('\n1. ', '\n<li>')
        html_content = html_content.replace('`', '<code>').replace('</code>', '</code>')
        html_content = html_content.replace('\n\n', '</p><p>')
        html_content = f"<p>{html_content}</p>"
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Railway Token Access Guide - DataRift</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
                <div class="container">
                    <a class="navbar-brand" href="/">DataRift</a>
                    <div class="navbar-nav ms-auto">
                        <a class="nav-link" href="/">Home</a>
                        <a class="nav-link" href="/dashboard">Dashboard</a>
                        <a class="nav-link" href="/tokens">Get Tokens</a>
                    </div>
                </div>
            </nav>
            
            <div class="container mt-5">
                <div class="row justify-content-center">
                    <div class="col-md-10">
                        <div class="card">
                            <div class="card-body">
                                {html_content}
                                <div class="text-center mt-4">
                                    <a href="/tokens" class="btn btn-success btn-lg">Get Tokens Now</a>
                                    <a href="/dashboard" class="btn btn-secondary">← Back to Dashboard</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    except FileNotFoundError:
        return "Guide not found", 404

@app.route("/debug-session")
def debug_session():
    """Debug route to check session contents"""
    return {
        'session_keys': list(session.keys()),
        'has_access_token': 'access_token' in session,
        'has_company_id': 'company_id' in session,
        'access_token_preview': session.get('access_token', 'None')[:20] + '...' if session.get('access_token') else 'None',
        'company_id': session.get('company_id', 'None')
    }

@app.route("/api/tokens")
def get_tokens_json():
    """Get QuickBooks tokens as JSON for easy copying"""
    if 'access_token' not in session:
        return jsonify({"error": "Not authenticated. Please connect to QuickBooks first."}), 401
    
    return jsonify({
        "access_token": session.get('access_token'),
        "company_id": session.get('company_id'),
        "expires_in": session.get('expires_in'),
        "refresh_token": session.get('refresh_token'),
        "status": "success",
        "message": "Copy these tokens to your Jupyter notebook"
    })

@app.route("/tokens")
def display_tokens():
    """Display QuickBooks tokens for copying to local Jupyter notebook"""
    if 'access_token' not in session:
        return redirect(url_for('auth'))
    
    access_token = session.get('access_token')
    company_id = session.get('company_id')
    
    # Detect if we're on Railway
    is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'))
    environment_name = "Railway (Production)" if is_railway else "Local Development"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QuickBooks Tokens - DataRift</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .token-box {{
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 0.375rem;
                padding: 1rem;
                font-family: 'Courier New', monospace;
                font-size: 0.9rem;
                word-break: break-all;
            }}
            .copy-btn {{
                margin-top: 0.5rem;
            }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/">DataRift</a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/">Home</a>
                    <a class="nav-link" href="/dashboard">Dashboard</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-10">
                    <div class="card">
                        <div class="card-header">
                            <h3 class="mb-0">🔑 QuickBooks API Tokens</h3>
                            <small class="text-muted">Environment: {environment_name}</small>
                        </div>
                        <div class="card-body">
                            
                            <div class="alert alert-success">
                                <h5>✅ Ready for Local Jupyter!</h5>
                                <p class="mb-0">Copy the tokens below and paste them into your local Jupyter notebook to start analyzing your QuickBooks data.</p>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Access Token:</h5>
                                <div class="token-box" id="access-token">{access_token}</div>
                                <button class="btn btn-sm btn-outline-primary copy-btn" onclick="copyToClipboard('access-token')">
                                    📋 Copy Access Token
                                </button>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Company ID:</h5>
                                <div class="token-box" id="company-id">{company_id}</div>
                                <button class="btn btn-sm btn-outline-primary copy-btn" onclick="copyToClipboard('company-id')">
                                    📋 Copy Company ID
                                </button>
                            </div>
                            
                            <div class="mb-4">
                                <h5>Quick Copy (Both Tokens):</h5>
                                <div class="token-box" id="both-tokens">ACCESS_TOKEN = "{access_token}"
COMPANY_ID = "{company_id}"</div>
                                <button class="btn btn-sm btn-success copy-btn" onclick="copyToClipboard('both-tokens')">
                                    📋 Copy Both (Ready to Paste)
                                </button>
                            </div>
                            
                            <div class="alert alert-info">
                                <h6>How to use in Jupyter:</h6>
                                <ol>
                                    <li>Start Jupyter locally: <code>jupyter lab</code></li>
                                    <li>Open <code>quickbooks_api_notebook.ipynb</code></li>
                                    <li>Paste the tokens in the authentication cell</li>
                                    <li>Run all cells to start analyzing!</li>
                                </ol>
                                
                                {f'''
                                <div class="mt-3 p-3 bg-light rounded">
                                    <strong>🚀 Railway Access:</strong><br>
                                    You're accessing tokens from your deployed Railway app! This means:
                                    <ul class="mb-0 mt-2">
                                        <li>✅ These are live production tokens</li>
                                        <li>✅ No local OAuth setup needed</li>
                                        <li>✅ Use these tokens in your local Jupyter notebook</li>
                                        <li>⚠️ Keep these tokens secure - don't share them</li>
                                    </ul>
                                </div>
                                ''' if is_railway else ''}
                            </div>
                            
                            <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                <a href="/dashboard" class="btn btn-secondary">← Back to Dashboard</a>
                                <button class="btn btn-primary" onclick="window.location.reload()">🔄 Refresh Tokens</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function copyToClipboard(elementId) {{
                const element = document.getElementById(elementId);
                const text = element.textContent;
                
                navigator.clipboard.writeText(text).then(function() {{
                    // Show success feedback
                    const button = element.nextElementSibling;
                    const originalText = button.textContent;
                    button.textContent = '✅ Copied!';
                    button.className = 'btn btn-sm btn-success copy-btn';
                    
                    setTimeout(() => {{
                        button.textContent = originalText;
                        button.className = 'btn btn-sm btn-outline-primary copy-btn';
                    }}, 2000);
                }}).catch(function(err) {{
                    alert('Failed to copy: ' + err);
                }});
            }}
        </script>
    </body>
    </html>
    """

# Jupyter Routes
@app.route("/jupyter")
def jupyter_home():
    """Jupyter notebook access page"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DataRift - Jupyter Notebook</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/">DataRift</a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/">Home</a>
                    <a class="nav-link" href="/dashboard">Dashboard</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h3 class="mb-0">🪐 Jupyter Notebook Access</h3>
                        </div>
                        <div class="card-body">
                            <div class="mb-4">
                                <h5>Status: <span id="jupyter-status" class="badge bg-secondary">Checking...</span></h5>
                            </div>
                            
                            <div class="alert alert-info">
                                <strong>Development Note:</strong> If you're running locally and Jupyter packages aren't installed, 
                                the start button won't work. This is normal - it will work when deployed to Railway where all 
                                dependencies are installed.
                            </div>
                            
                            <div class="mb-4">
                                <h6>Access Information:</h6>
                                <ul class="list-unstyled">
                                    <li><strong>Port:</strong> {JUPYTER_PORT}</li>
                                    <li><strong>Token:</strong> <code>{JUPYTER_PASSWORD}</code></li>
                                    <li><strong>Notebook:</strong> <code>quickbooks_api_notebook.ipynb</code></li>
                                </ul>
                            </div>
                            
                            <div class="d-grid gap-2">
                                <button id="start-jupyter" class="btn btn-success" onclick="startJupyter()">
                                    🚀 Start Jupyter Lab
                                </button>
                                <button id="stop-jupyter" class="btn btn-danger" onclick="stopJupyter()" disabled>
                                    🛑 Stop Jupyter Lab
                                </button>
                                <a id="open-jupyter" href="#" class="btn btn-primary" target="_blank" style="display:none;">
                                    📓 Open Jupyter Lab
                                </a>
                            </div>
                            
                            <div class="mt-4">
                                <h6>Quick Start:</h6>
                                <ol>
                                    <li>Click "Start Jupyter Lab" above</li>
                                    <li>Wait for the server to start (may take 30-60 seconds)</li>
                                    <li>Click "Open Jupyter Lab" when available</li>
                                    <li>Enter token: <code>{JUPYTER_PASSWORD}</code></li>
                                    <li>Open <code>quickbooks_api_notebook.ipynb</code></li>
                                </ol>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function checkStatus() {{
                fetch('/jupyter/status')
                    .then(response => response.json())
                    .then(data => {{
                        const statusBadge = document.getElementById('jupyter-status');
                        const startBtn = document.getElementById('start-jupyter');
                        const stopBtn = document.getElementById('stop-jupyter');
                        const openBtn = document.getElementById('open-jupyter');
                        
                        if (data.running) {{
                            statusBadge.textContent = 'Running';
                            statusBadge.className = 'badge bg-success';
                            startBtn.disabled = true;
                            stopBtn.disabled = false;
                            openBtn.style.display = 'block';
                            // Use Flask proxy route for Jupyter
                            openBtn.href = `/jupyter-lab/?token=${{data.token}}`;
                        }} else {{
                            statusBadge.textContent = 'Stopped';
                            statusBadge.className = 'badge bg-danger';
                            startBtn.disabled = false;
                            stopBtn.disabled = true;
                            openBtn.style.display = 'none';
                        }}
                    }});
            }}
            
            function startJupyter() {{
                document.getElementById('start-jupyter').disabled = true;
                document.getElementById('jupyter-status').textContent = 'Starting...';
                document.getElementById('jupyter-status').className = 'badge bg-warning';
                
                fetch('/jupyter/start', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            setTimeout(checkStatus, 2000);
                        }} else {{
                            let errorMsg = 'Failed to start Jupyter: ' + data.error;
                            if (data.details) {{
                                errorMsg += '\\n\\nDetails: ' + data.details;
                            }}
                            alert(errorMsg);
                            checkStatus();
                        }}
                    }})
                    .catch(error => {{
                        alert('Network error starting Jupyter: ' + error.message);
                        checkStatus();
                    }});
            }}
            
            function stopJupyter() {{
                fetch('/jupyter/stop', {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        checkStatus();
                    }});
            }}
            
            // Check status on page load and every 10 seconds
            checkStatus();
            setInterval(checkStatus, 10000);
        </script>
    </body>
    </html>
    """

@app.route("/jupyter/status")
def jupyter_status():
    """Get Jupyter server status"""
    return jsonify({
        'running': is_jupyter_running(),
        'port': JUPYTER_PORT,
        'token': JUPYTER_PASSWORD
    })

@app.route("/jupyter/start", methods=['POST'])
def start_jupyter_route():
    """Start Jupyter server"""
    try:
        print("📡 Received request to start Jupyter server")
        success = start_jupyter_server()
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'Jupyter server started successfully',
                'port': JUPYTER_PORT
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Failed to start Jupyter server. Check server logs for details.',
                'details': 'Jupyter may not be installed or there may be a port conflict.'
            })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Exception in start_jupyter_route: {error_details}")
        
        return jsonify({
            'success': False, 
            'error': str(e),
            'details': 'Check server logs for full error details.'
        })

@app.route("/jupyter/stop", methods=['POST'])
def stop_jupyter():
    """Stop Jupyter server"""
    try:
        stop_jupyter_server()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route("/jupyter-lab/")
def jupyter_redirect():
    """Redirect to Jupyter Lab with instructions"""
    if not is_jupyter_running():
        return """
        <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
            <h2>Jupyter Lab is not running</h2>
            <p>Please go back to the <a href="/jupyter">Jupyter management page</a> and start the server first.</p>
        </div>
        """, 503
    
    # Get the current domain but determine the correct Jupyter URL
    current_domain = request.host.split(':')[0]  # Remove port if present
    
    # Determine the correct Jupyter URL based on environment
    if 'localhost' in current_domain or '127.0.0.1' in current_domain:
        # Development environment
        jupyter_url = f"http://localhost:{JUPYTER_PORT}/?token={JUPYTER_PASSWORD}"
        railway_url_option1 = jupyter_url
        railway_url_option2 = jupyter_url
    else:
        # Production environment (Railway)
        # Railway may expose Jupyter on the same domain with a different subdomain or port
        railway_url_option1 = f"https://{current_domain.replace('app', 'jupyter')}/?token={JUPYTER_PASSWORD}"
        railway_url_option2 = f"https://{current_domain}:{JUPYTER_PORT}/?token={JUPYTER_PASSWORD}"
        jupyter_url = railway_url_option1  # Try the subdomain approach first
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Jupyter Lab Access</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h3>🪐 Jupyter Lab Access</h3>
                        </div>
                        <div class="card-body text-center">
                            <h5>Jupyter Lab is running!</h5>
                            <p class="mb-4">Click the button below to access Jupyter Lab:</p>
                            
                            <div class="mb-4">
                                <strong>Access Token:</strong> <code>{JUPYTER_PASSWORD}</code>
                            </div>
                            
                            <div class="d-grid gap-2">
                                <a href="{jupyter_url}" target="_blank" class="btn btn-success btn-lg">
                                    🚀 Open Jupyter Lab
                                </a>
                                <a href="/jupyter" class="btn btn-secondary">
                                    ← Back to Management
                                </a>
                            </div>
                            
                            <div class="mt-4 text-start">
                                <h6>If the main link doesn't work, try these alternatives:</h6>
                                <div class="mb-3">
                                    <strong>Option 1 (Subdomain):</strong><br>
                                    <code>{railway_url_option1}</code>
                                </div>
                                <div class="mb-3">
                                    <strong>Option 2 (Port):</strong><br>
                                    <code>{railway_url_option2}</code>
                                </div>
                                <div class="alert alert-info">
                                    <strong>Railway Note:</strong> Railway may need additional configuration to expose port {JUPYTER_PORT}. 
                                    Check your Railway dashboard for service URLs or contact support if needed.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def startup():
    """Initialize services when Flask starts"""
    # Start Jupyter server in background thread
    def start_jupyter_background():
        time.sleep(5)  # Give Flask time to fully start
        start_jupyter_server()
    
    jupyter_thread = threading.Thread(target=start_jupyter_background, daemon=True)
    jupyter_thread.start()

import atexit

def cleanup():
    """Cleanup when Flask shuts down"""
    stop_jupyter_server()

atexit.register(cleanup)

if __name__ == '__main__':
    # Start Jupyter server in background
    startup()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
# QBO-Style Transaction Table - Updated Sat Sep 20 18:18:18 EDT 2025
