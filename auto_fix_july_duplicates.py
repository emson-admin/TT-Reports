import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

def auto_fix_july_duplicates():
    # Load credentials
    with open('credentials.json', 'r') as f:
        credentials_info = json.load(f)
    
    # Connect to Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(credentials_info, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('TikTok GMVMAX Ad Reports').worksheet('Data')
    
    # Get all data including headers
    print("Fetching data from Google Sheet...")
    all_values = sh.get_all_values()
    
    if len(all_values) < 2:
        print("Sheet has no data!")
        return
    
    # First row is headers, rest is data
    headers = all_values[0]
    data = all_values[1:]
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    if df.empty:
        print("Sheet is empty!")
        return
    
    # Store original column names (headers)
    original_cols = headers
    
    # Normalize column names for processing
    df.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in df.columns])
    
    # Convert report_date to datetime
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    
    # Separate July data and non-July data
    july_mask = df['report_date'].dt.month == 7
    july_data = df[july_mask].copy()
    non_july_data = df[~july_mask].copy()
    
    print(f"\n=== JULY DUPLICATE REMOVAL ===")
    print(f"Total July rows before deduplication: {len(july_data)}")
    print(f"Total non-July rows: {len(non_july_data)}")
    
    # Remove duplicates from July data (keep first occurrence)
    july_deduplicated = july_data.drop_duplicates(subset=['campaign_id', 'report_date'], keep='first')
    duplicates_removed = len(july_data) - len(july_deduplicated)
    
    print(f"\nJuly rows after deduplication: {len(july_deduplicated)}")
    print(f"Rows removed from July: {duplicates_removed}")
    
    # Calculate the financial impact
    if 'cost' in july_data.columns and 'gross_revenue' in july_data.columns:
        # Convert to numeric for calculations
        july_cost_before = pd.to_numeric(july_data['cost'], errors='coerce').sum()
        july_revenue_before = pd.to_numeric(july_data['gross_revenue'], errors='coerce').sum()
        july_cost_after = pd.to_numeric(july_deduplicated['cost'], errors='coerce').sum()
        july_revenue_after = pd.to_numeric(july_deduplicated['gross_revenue'], errors='coerce').sum()
        
        print(f"\n--- FINANCIAL IMPACT ---")
        print(f"July total cost before: ${july_cost_before:.2f}")
        print(f"July total cost after: ${july_cost_after:.2f}")
        print(f"Cost reduction: ${july_cost_before - july_cost_after:.2f}")
        print(f"\nJuly revenue before: ${july_revenue_before:.2f}")
        print(f"July revenue after: ${july_revenue_after:.2f}")
        print(f"Revenue adjustment: ${july_revenue_before - july_revenue_after:.2f}")
    
    if duplicates_removed > 0:
        print("\n✅ Proceeding with automatic duplicate removal...")
        
        # Combine deduplicated July with non-July data
        final_df = pd.concat([non_july_data, july_deduplicated], ignore_index=True)
        
        # Sort by date for better organization
        final_df = final_df.sort_values('report_date')
        
        print(f"Final total rows: {len(final_df)}")
        
        # Convert datetime columns to string
        for col in final_df.select_dtypes(include=['datetime', 'datetime64[ns]']).columns:
            final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')
        
        # Clear and rewrite the sheet
        print("\nClearing sheet and uploading fixed data...")
        sh.clear()
        
        # Prepare data for upload with original column names
        data_rows = final_df.astype(str).values.tolist()
        all_data_to_upload = [original_cols] + data_rows
        
        # Upload fixed data
        sh.update('A1', all_data_to_upload)
        
        print(f"\n✅ Successfully removed {duplicates_removed} duplicate July rows!")
        print(f"✅ Sheet now contains {len(final_df)} total rows.")
        print(f"✅ July costs corrected from ${july_cost_before:.2f} to ${july_cost_after:.2f}")
        
        # Clear the Streamlit cache to reflect changes
        print("\n⚠️  Please refresh your Streamlit app to see the updated data.")
    else:
        print("\n✅ No duplicate rows found in July data!")

if __name__ == "__main__":
    try:
        auto_fix_july_duplicates()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()