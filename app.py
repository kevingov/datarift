from flask import Flask, render_template, redirect, url_for, session, request, flash, jsonify
import os
from dotenv import load_dotenv
import requests
import uuid
import json
from urllib.parse import quote_plus
import base64

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
@app.route('/tokens')

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
        ("SalesReceipt", "Sales Receipt")
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
        ("SalesReceipt", "Sales Receipt")
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
# QBO-Style Transaction Table - Updated Sat Sep 20 18:18:18 EDT 2025
