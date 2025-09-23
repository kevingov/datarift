# Improved QuickBooks data extraction with pagination and CSV export

def make_paginated_api_call(entity_type, max_results=1000):
    """Fetch ALL records from QuickBooks with pagination"""
    if 'access_token' not in session or 'company_id' not in session:
        return {"error": "Not connected to QuickBooks"}, 401

    access_token = session['access_token']
    company_id = session['company_id']
    
    all_records = []
    start_position = 1
    page_size = 100  # QuickBooks max per page
    
    while True:
        # Build query with pagination
        query = f"SELECT * FROM {entity_type} STARTPOSITION {start_position} MAXRESULTS {page_size}"
        encoded_query = quote_plus(query)
        
        url = f"{QB_API_BASE_URL}/{company_id}/query?query={encoded_query}&minorversion=69"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        try:
            print(f"Fetching {entity_type} - Page starting at {start_position}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Get records from response
            query_response = data.get('QueryResponse', {})
            records = query_response.get(entity_type, [])
            
            if not records:
                print(f"No more {entity_type} records found")
                break
                
            all_records.extend(records)
            
            # Check if we got less than page_size (last page)
            if len(records) < page_size:
                print(f"Last page reached for {entity_type}")
                break
                
            start_position += page_size
            
            # Safety limit
            if len(all_records) >= max_results:
                print(f"Reached max results limit ({max_results}) for {entity_type}")
                break
                
        except Exception as e:
            print(f"Error fetching {entity_type} page {start_position}: {str(e)}")
            if response:
                print(f"Response: {response.text}")
            break
    
    print(f"Total {entity_type} records fetched: {len(all_records)}")
    return all_records

@app.route('/api/export/all-transactions-csv')
def export_all_transactions_csv():
    """Export ALL transaction data as CSV with proper pagination"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    
    all_data = []
    
    # All transaction types in QuickBooks
    transaction_types = [
        "JournalEntry", "Invoice", "Payment", "Bill", "BillPayment", 
        "Deposit", "Purchase", "Expense", "Transfer", "CreditMemo", 
        "SalesReceipt", "RefundReceipt", "VendorCredit", "EstimateLinkedTxn"
    ]
    
    for entity_type in transaction_types:
        try:
            print(f"\n=== Fetching ALL {entity_type} records ===")
            records = make_paginated_api_call(entity_type)
            
            if isinstance(records, tuple):  # Error case
                print(f"Error fetching {entity_type}: {records[0]}")
                continue
                
            for record in records:
                # Flatten the record for CSV
                flat_record = flatten_qb_record(record, entity_type)
                all_data.append(flat_record)
                
        except Exception as e:
            print(f"Error processing {entity_type}: {str(e)}")
            continue
    
    if not all_data:
        return jsonify({"error": "No transaction data found"}), 404
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data)
    
    # Sort by date if available
    if 'TxnDate' in df.columns:
        df['TxnDate'] = pd.to_datetime(df['TxnDate'], errors='coerce')
        df = df.sort_values('TxnDate', ascending=False)
        df['TxnDate'] = df['TxnDate'].dt.strftime('%Y-%m-%d')
    
    # Create CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=quickbooks_all_transactions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )

def flatten_qb_record(record, entity_type):
    """Flatten a QuickBooks record into a flat dictionary for CSV export"""
    flat = {
        'Entity_Type': entity_type,
        'ID': record.get('Id', ''),
        'SyncToken': record.get('SyncToken', ''),
        'TxnDate': record.get('TxnDate', ''),
        'DocNumber': record.get('DocNumber', ''),
        'TotalAmt': record.get('TotalAmt', 0),
        'Balance': record.get('Balance', 0),
        'CurrencyRef': record.get('CurrencyRef', {}).get('value', ''),
        'PrivateNote': record.get('PrivateNote', ''),
        'Memo': record.get('Memo', ''),
        'TxnStatus': record.get('TxnStatus', ''),
        'TxnSource': record.get('TxnSource', ''),
        'LineCount': record.get('LineCount', 0),
        'CreateTime': record.get('MetaData', {}).get('CreateTime', ''),
        'LastUpdatedTime': record.get('MetaData', {}).get('LastUpdatedTime', ''),
    }
    
    # Add customer info
    if 'CustomerRef' in record:
        flat['Customer_ID'] = record['CustomerRef'].get('value', '')
        flat['Customer_Name'] = record['CustomerRef'].get('name', '')
    
    # Add vendor info
    if 'VendorRef' in record:
        flat['Vendor_ID'] = record['VendorRef'].get('value', '')
        flat['Vendor_Name'] = record['VendorRef'].get('name', '')
    
    # Add account info
    if 'AccountRef' in record:
        flat['Account_ID'] = record['AccountRef'].get('value', '')
        flat['Account_Name'] = record['AccountRef'].get('name', '')
    
    # Add payment method
    if 'PaymentMethodRef' in record:
        flat['PaymentMethod_ID'] = record['PaymentMethodRef'].get('value', '')
        flat['PaymentMethod_Name'] = record['PaymentMethodRef'].get('name', '')
    
    # Process line items
    if 'Line' in record and record['Line']:
        line_items = []
        for i, line in enumerate(record['Line']):
            line_prefix = f'Line_{i+1}_'
            flat[f'{line_prefix}ID'] = line.get('Id', '')
            flat[f'{line_prefix}LineNum'] = line.get('LineNum', '')
            flat[f'{line_prefix}Description'] = line.get('Description', '')
            flat[f'{line_prefix}Amount'] = line.get('Amount', 0)
            flat[f'{line_prefix}DetailType'] = line.get('DetailType', '')
            
            # Handle different detail types
            for detail_type in ['SalesItemLineDetail', 'AccountBasedExpenseLineDetail', 
                              'JournalEntryLineDetail', 'DepositLineDetail', 'ItemBasedExpenseLineDetail']:
                if detail_type in line:
                    detail = line[detail_type]
                    if 'AccountRef' in detail:
                        flat[f'{line_prefix}Account_ID'] = detail['AccountRef'].get('value', '')
                        flat[f'{line_prefix}Account_Name'] = detail['AccountRef'].get('name', '')
                    if 'ItemRef' in detail:
                        flat[f'{line_prefix}Item_ID'] = detail['ItemRef'].get('value', '')
                        flat[f'{line_prefix}Item_Name'] = detail['ItemRef'].get('name', '')
                    if 'ClassRef' in detail:
                        flat[f'{line_prefix}Class_ID'] = detail['ClassRef'].get('value', '')
                        flat[f'{line_prefix}Class_Name'] = detail['ClassRef'].get('name', '')
                    break
    
    # Add the full JSON as a string for reference
    flat['Full_JSON'] = str(record)
    
    return flat

@app.route('/api/export/summary-csv')
def export_summary_csv():
    """Export a summary of all transaction types and counts"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    
    transaction_types = [
        "JournalEntry", "Invoice", "Payment", "Bill", "BillPayment", 
        "Deposit", "Purchase", "Expense", "Transfer", "CreditMemo", 
        "SalesReceipt", "RefundReceipt", "VendorCredit"
    ]
    
    summary_data = []
    
    for entity_type in transaction_types:
        try:
            # Get count using COUNT query
            count_query = f"SELECT COUNT(*) FROM {entity_type}"
            result = make_quickbooks_api_call(count_query)
            
            if isinstance(result, tuple):
                count = 0
                error = result[0].get('error', 'Unknown error')
            else:
                count = result.get('QueryResponse', {}).get('totalCount', 0)
                error = None
            
            summary_data.append({
                'Entity_Type': entity_type,
                'Total_Records': count,
                'Status': 'Success' if error is None else 'Error',
                'Error_Message': error or ''
            })
            
        except Exception as e:
            summary_data.append({
                'Entity_Type': entity_type,
                'Total_Records': 0,
                'Status': 'Error',
                'Error_Message': str(e)
            })
    
    df = pd.DataFrame(summary_data)
    
    # Create CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=quickbooks_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )
