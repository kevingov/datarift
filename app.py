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
            .hero-section {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 100px 0;
            }

            function loadPandasTransactions() {
                const tbody = document.getElementById('pandas-transactions-tbody');
                const summary = document.getElementById('pandas-summary');
                const stats = document.getElementById('pandas-stats');
                
                // Show loading state
                tbody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Loading transactions...</td></tr>';
                
                fetch('/api/transactions/pandas')
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error: ${data.error}</td></tr>`;
                            return;
                        }
                        
                        const transactions = data.transactions || [];
                        const summary_data = data.summary || {};
                        const pandas_info = data.pandas_info || {};
                        
                        // Update summary with enhanced stats
                        let summaryHtml = '<div class="row">';
                        summaryHtml += `<div class="col-md-3"><div class="card bg-primary text-white"><div class="card-body text-center"><h6>Total Transactions</h6><h4>${data.total_count || 0}</h4></div></div></div>`;
                        summaryHtml += `<div class="col-md-3"><div class="card bg-success text-white"><div class="card-body text-center"><h6>Total Amount</h6><h4>$${(summary_data.total_amount || 0).toFixed(2)}</h4></div></div></div>`;
                        summaryHtml += `<div class="col-md-3"><div class="card bg-info text-white"><div class="card-body text-center"><h6>Average Amount</h6><h4>$${(summary_data.average_amount || 0).toFixed(2)}</h4></div></div></div>`;
                        summaryHtml += `<div class="col-md-3"><div class="card bg-warning text-white"><div class="card-body text-center"><h6>Date Range</h6><h6>${summary_data.date_range?.earliest || 'N/A'} to ${summary_data.date_range?.latest || 'N/A'}</h6></div></div></div>`;
                        summaryHtml += '</div>';
                        
                        // Add type breakdown
                        if (summary_data.by_type) {
                            summaryHtml += '<div class="row mt-3"><div class="col-12"><h6>Transactions by Type:</h6>';
                            for (const [type, count] of Object.entries(summary_data.by_type)) {
                                summaryHtml += `<span class="badge bg-secondary me-2">${type}: ${count}</span>`;
                            }
                            summaryHtml += '</div></div>';
                        }
                        
                        summary.innerHTML = summaryHtml;
                        
                        // Update table
                        if (transactions.length === 0) {
                            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No transactions found</td></tr>';
                            return;
                        }
                        
                        tbody.innerHTML = transactions.map(transaction => `
                            <tr>
                                <td>${transaction.id || ''}</td>
                                <td><span class="badge bg-secondary">${transaction.type || ''}</span></td>
                                <td>${transaction.date || ''}</td>
                                <td class="text-end fw-bold">$${parseFloat(transaction.amount || 0).toFixed(2)}</td>
                                <td>${transaction.description || ''}</td>
                                <td>${transaction.reference || ''}</td>
                                <td><span class="badge bg-info">${transaction.status || ''}</span></td>
                                <td>${transaction.created_time || ''}</td>
                            </tr>
                        `).join('');
                        
                        // Add pandas statistics
                        let statsHtml = '<div class="row mt-3">';
                        statsHtml += `<div class="col-md-4"><small class="text-muted">Data Shape: ${pandas_info.shape?.[0] || 0} rows × ${pandas_info.shape?.[1] || 0} columns</small></div>`;
                        statsHtml += `<div class="col-md-4"><small class="text-muted">Memory Usage: ${pandas_info.memory_usage || 'N/A'}</small></div>`;
                        statsHtml += `<div class="col-md-4"><small class="text-muted">Columns: ${pandas_info.columns?.join(', ') || 'N/A'}</small></div>`;
                        statsHtml += '</div>';
                        stats.innerHTML = statsHtml;
                    })
                    .catch(error => {
                        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error: ${error.message}</td></tr>`;
                    });
            }

            function exportPandasCSV() {
                window.open('/api/transactions/export/pandas', '_blank');
            }

            function exportExcel() {
                window.open("/api/transactions/export/excel", "_blank");
            }

            function loadQBOTransactions() {
                const container = document.getElementById("qbo-transactions-container");
                const loading = document.getElementById("qbo-loading");
                
                loading.style.display = "block";
                container.innerHTML = "";
                
                fetch("/api/transactions/qbo-style")
                    .then(response => response.json())
                    .then(data => {
                        loading.style.display = "none";
                        
                        if (data.error) {
                            container.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                            return;
                        }
                        
                        if (data.transactions && data.transactions.length > 0) {
                            // Create QBO-style table
                            let tableHTML = `
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead class="table-dark">
                                            <tr>
                                                <th>Transaction Date</th>
                                                <th>Distribution Account</th>
                                                <th>Name</th>
                                                <th>Transaction Type</th>
                                                <th>Memo/Description</th>
                                                <th>Item Split Account</th>
                                                <th>Amount</th>
                                                <th>Customer</th>
                                                <th>Supplier</th>
                                                <th>Account Type</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                            `;
                            
                            data.transactions.forEach(transaction => {
                                const amountClass = transaction.Amount < 0 ? "text-danger" : "text-success";
                                tableHTML += `
                                    <tr>
                                        <td>${transaction["Transaction date"] || ""}</td>
                                        <td>${transaction["Distribution account"] || ""}</td>
                                        <td>${transaction["Name"] || ""}</td>
                                        <td>${transaction["Transaction type"] || ""}</td>
                                        <td>${transaction["Memo/Description"] || ""}</td>
                                        <td>${transaction["Item split account full name"] || ""}</td>
                                        <td class="${amountClass}">$${Math.abs(transaction.Amount).toFixed(2)}</td>
                                        <td>${transaction["Customer"] || ""}</td>
                                        <td>${transaction["Supplier"] || ""}</td>
                                        <td>${transaction["Distribution account type"] || ""}</td>
                                    </tr>
                                `;
                            });
                            
                            tableHTML += `
                                        </tbody>
                                    </table>
                                </div>
                            `;
                            
                            // Add summary cards
                            if (data.summary) {
                                tableHTML += `
                                    <div class="row mt-3">
                                        <div class="col-md-3">
                                            <div class="card bg-primary text-white">
                                                <div class="card-body text-center">
                                                    <h6>Total Transactions</h6>
                                                    <h4>${data.total_count}</h4>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="card bg-success text-white">
                                                <div class="card-body text-center">
                                                    <h6>Total Amount</h6>
                                                    <h4>$${data.summary.total_amount ? data.summary.total_amount.toFixed(2) : "0.00"}</h4>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="card bg-info text-white">
                                                <div class="card-body text-center">
                                                    <h6>Average Amount</h6>
                                                    <h4>$${data.summary.average_amount ? data.summary.average_amount.toFixed(2) : "0.00"}</h4>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="card bg-warning text-white">
                                                <div class="card-body text-center">
                                                    <h6>Date Range</h6>
                                                    <small>${data.summary.date_range.earliest} to ${data.summary.date_range.latest}</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }
                            
                            container.innerHTML = tableHTML;
                        } else {
                            container.innerHTML = "<div class=\"alert alert-info\">No QBO-style transaction data available</div>";
                        }
                    })
                    .catch(error => {
                        loading.style.display = "none";
                        container.innerHTML = `<div class="alert alert-danger">Error loading QBO transactions: ${error.message}</div>`;
                    });
            }

            function exportQBOTransactions() {
                window.open("/api/transactions/export/qbo-style", "_blank");
            }

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

@app.route('/tokens')

# QBO-Style Transaction Endpoint
@app.route('/api/transactions/qbo-style')
def get_transactions_qbo_style():
    """Get all transactions formatted like QBO export"""
    if 'access_token' not in session or 'company_id' not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    from datetime import datetime
    
    unified_transactions = []
    
    # Helper function to convert QB data to QBO export format
    def convert_to_qbo_format(transaction, transaction_type):
        """Convert QuickBooks transaction to QBO export format"""
        
        # Base QBO export structure
        qbo_row = {
            'Transaction date': '',
            'Distribution account': '',
            'Name': '',
            'Transaction type': '',
            'Transaction type_2': '',  # Duplicate column as in QBO
            'Memo/Description': '',
            'Item split account full name': '',
            'Amount': 0,
            'Customer': '',
            'Full name': '',
            'Supplier': '',
            'Distribution account type': '',
            'Item class': '',
            'Class full name': ''
        }
        
        # Set transaction date
        qbo_row['Transaction date'] = transaction.get('TxnDate', '')
        
        # Set transaction type
        qbo_row['Transaction type'] = transaction_type
        qbo_row['Transaction type_2'] = transaction_type
        
        # Extract amount and set as negative for expenses
        amount = 0
        if transaction_type in ['Bill', 'Bill Payment (Cheque)', 'Expense']:
            amount = -abs(float(transaction.get('TotalAmt', 0)))
        else:
            amount = float(transaction.get('TotalAmt', 0))
        
        qbo_row['Amount'] = amount
        
        # Process based on transaction type
        if transaction_type == 'JournalEntry':
            qbo_row['Name'] = transaction.get('DocNumber', 'Journal Entry')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            
            # Process journal entry lines
            for line in transaction.get('Line', []):
                if line.get('DetailType') == 'JournalEntryLineDetail':
                    detail = line.get('JournalEntryLineDetail', {})
                    account = detail.get('AccountRef', {})
                    qbo_row['Distribution account'] = account.get('name', '')
                    qbo_row['Item split account full name'] = account.get('name', '')
                    qbo_row['Distribution account type'] = 'Other'  # Default
                    break
                    
        elif transaction_type == 'Deposit':
            qbo_row['Name'] = transaction.get('DocNumber', 'Deposit')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            qbo_row['Distribution account'] = 'Bank Account'  # Default
            qbo_row['Distribution account type'] = 'Bank'
            
        elif transaction_type == 'Purchase':
            qbo_row['Name'] = transaction.get('DocNumber', 'Purchase')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            qbo_row['Distribution account'] = 'Accounts Payable'
            qbo_row['Distribution account type'] = 'Accounts payable (A/P)'
            
            # Get vendor info
            vendor_ref = transaction.get('VendorRef', {})
            qbo_row['Supplier'] = vendor_ref.get('name', '')
            qbo_row['Full name'] = vendor_ref.get('name', '')
            
        elif transaction_type == 'Transfer':
            qbo_row['Name'] = transaction.get('DocNumber', 'Transfer')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            qbo_row['Distribution account'] = 'Bank Account'
            qbo_row['Distribution account type'] = 'Bank'
            
        elif transaction_type == 'Payment':
            qbo_row['Name'] = transaction.get('DocNumber', 'Payment')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            qbo_row['Distribution account'] = 'Bank Account'
            qbo_row['Distribution account type'] = 'Bank'
            
            # Get customer info
            customer_ref = transaction.get('CustomerRef', {})
            qbo_row['Customer'] = customer_ref.get('name', '')
            qbo_row['Full name'] = customer_ref.get('name', '')
            
        elif transaction_type == 'Invoice':
            qbo_row['Name'] = transaction.get('DocNumber', 'Invoice')
            qbo_row['Memo/Description'] = transaction.get('DocNumber', '')
            qbo_row['Distribution account'] = 'Accounts Receivable'
            qbo_row['Distribution account type'] = 'Accounts receivable (A/R)'
            
            # Get customer info
            customer_ref = transaction.get('CustomerRef', {})
            qbo_row['Customer'] = customer_ref.get('name', '')
            qbo_row['Full name'] = customer_ref.get('name', '')
        
        return qbo_row
    
    # Fetch all transaction types
    transaction_types = [
        ('JournalEntry', 'Journal Entry'),
        ('Deposit', 'Deposit'),
        ('Purchase', 'Bill'),
        ('Transfer', 'Transfer'),
        ('Payment', 'Payment'),
        ('Invoice', 'Invoice')
    ]
    
    for entity_type, qbo_type in transaction_types:
        try:
            result = make_quickbooks_api_call(f"SELECT * FROM {entity_type}")
            
            if isinstance(result, tuple):
                print(f"Error fetching {qbo_type}: {result[0]}")
                continue
                
            transactions = result.get('QueryResponse', {}).get(entity_type, [])
            
            for transaction in transactions:
                qbo_formatted = convert_to_qbo_format(transaction, qbo_type)
                unified_transactions.append(qbo_formatted)
                
        except Exception as e:
            print(f"Error processing {qbo_type}: {str(e)}")
            continue
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(unified_transactions)
    
    if df.empty:
        return jsonify({
            'transactions': [],
            'total_count': 0,
            'summary': {},
            'qbo_format': True
        })
    
    # Convert date column to datetime and sort
    df['Transaction date'] = pd.to_datetime(df['Transaction date'], errors='coerce')
    df = df.sort_values('Transaction date', ascending=False)
    
    # Format date back to string for JSON
    df['Transaction date'] = df['Transaction date'].dt.strftime('%Y/%m/%d')
    
    # Create summary statistics
    summary = {
        'by_type': df['Transaction type'].value_counts().to_dict(),
        'total_amount': df['Amount'].sum(),
        'average_amount': df['Amount'].mean(),
        'date_range': {
            'earliest': df['Transaction date'].min() if not df['Transaction date'].isna().all() else 'N/A',
            'latest': df['Transaction date'].max() if not df['Transaction date'].isna().all() else 'N/A'
        },
        'amount_by_type': df.groupby('Transaction type')['Amount'].sum().to_dict()
    }
    
    # Convert DataFrame back to list of dictionaries for JSON response
    transactions_list = df.fillna('').to_dict('records')
    
    return jsonify({
        'transactions': transactions_list,
        'total_count': len(transactions_list),
        'summary': summary,
        'qbo_format': True,
        'columns': list(df.columns)
    })

# QBO-Style CSV Export
@app.route('/api/transactions/export/qbo-style')
def export_transactions_qbo_style():
    """Export transactions in QBO export format"""
    if 'access_token' not in session or 'company_id' not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    from flask import Response
    
    # Get the QBO-style transaction data
    transactions_data = get_transactions_qbo_style()
    if isinstance(transactions_data, tuple):
        return transactions_data
    
    transactions = transactions_data.get_json()['transactions']
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    if df.empty:
        return Response("No data available", mimetype='text/csv')
    
    # Create CSV content with QBO-style formatting
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8')
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=quickbooks_transactions_qbo_style.csv'}
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
