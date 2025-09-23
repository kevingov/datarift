# New functions for getting ALL raw data with pagination

def make_paginated_api_call(entity_type, max_results=5000):
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

@app.route('/api/raw-data-all')
def get_all_raw_data():
    """Get ALL raw data from QuickBooks in one giant pandas DataFrame"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    from datetime import datetime
    
    all_data = []
    
    # All entity types in QuickBooks
    entity_types = [
        "Customer", "Vendor", "Item", "Account", "Class", "Department",
        "JournalEntry", "Invoice", "Payment", "Bill", "BillPayment", 
        "Deposit", "Purchase", "Expense", "Transfer", "CreditMemo", 
        "SalesReceipt", "RefundReceipt", "VendorCredit", "Estimate",
        "TaxRate", "TaxCode", "Currency", "CompanyInfo"
    ]
    
    for entity_type in entity_types:
        try:
            print(f"\n=== Fetching ALL {entity_type} records ===")
            records = make_paginated_api_call(entity_type)
            
            if isinstance(records, tuple):  # Error case
                print(f"Error fetching {entity_type}: {records[0]}")
                continue
                
            for record in records:
                # Add entity type to each record
                record['_EntityType'] = entity_type
                all_data.append(record)
                
        except Exception as e:
            print(f"Error processing {entity_type}: {str(e)}")
            continue
    
    if not all_data:
        return jsonify({"error": "No data found"}), 404
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(all_data)
    
    # Convert to JSON for API response
    result = {
        "total_records": len(df),
        "columns": list(df.columns),
        "data": df.to_dict('records'),
        "summary": {
            "by_entity_type": df['_EntityType'].value_counts().to_dict() if '_EntityType' in df.columns else {},
            "total_columns": len(df.columns)
        }
    }
    
    return jsonify(result)

@app.route('/api/raw-data-csv')
def download_all_raw_data_csv():
    """Download ALL raw data as CSV file"""
    if "access_token" not in session or "company_id" not in session:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    import pandas as pd
    import io
    
    all_data = []
    
    # All entity types in QuickBooks
    entity_types = [
        "Customer", "Vendor", "Item", "Account", "Class", "Department",
        "JournalEntry", "Invoice", "Payment", "Bill", "BillPayment", 
        "Deposit", "Purchase", "Expense", "Transfer", "CreditMemo", 
        "SalesReceipt", "RefundReceipt", "VendorCredit", "Estimate",
        "TaxRate", "TaxCode", "Currency", "CompanyInfo"
    ]
    
    for entity_type in entity_types:
        try:
            print(f"\n=== Fetching ALL {entity_type} records ===")
            records = make_paginated_api_call(entity_type)
            
            if isinstance(records, tuple):  # Error case
                print(f"Error fetching {entity_type}: {records[0]}")
                continue
                
            for record in records:
                # Add entity type to each record
                record['_EntityType'] = entity_type
                all_data.append(record)
                
        except Exception as e:
            print(f"Error processing {entity_type}: {str(e)}")
            continue
    
    if not all_data:
        return jsonify({"error": "No data found"}), 404
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(all_data)
    
    # Create CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=quickbooks_all_raw_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
    )
