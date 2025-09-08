import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

def fix_july_duplicates():
    # Load credentials
    with open('credentials.json', 'r') as f:
        credentials_info = json.load(f)
    
    # Connect to Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(credentials_info, scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('TikTok GMVMAX Ad Reports').worksheet('Data')
    
    # Get all data
    print("Fetching data from Google Sheet...")
    all_data = sh.get_all_records()
    df = pd.DataFrame(all_data)
    
    if df.empty:
        print("Sheet is empty!")
        return
    
    # Normalize column names for processing
    df.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in df.columns])
    
    # Convert report_date to datetime
    df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    
    # Separate July data and non-July data
    july_data = df[df['report_date'].dt.month == 7].copy()
    non_july_data = df[df['report_date'].dt.month != 7].copy()
    
    print(f"\n=== JULY DUPLICATE ANALYSIS ===")
    print(f"Total July rows before deduplication: {len(july_data)}")
    print(f"Total non-July rows: {len(non_july_data)}")
    
    # Check for duplicates by campaign_id and report_date in July
    july_duplicates = july_data.duplicated(subset=['campaign_id', 'report_date'], keep=False)
    print(f"July rows that are duplicates (by campaign_id + date): {july_duplicates.sum()}")
    
    # Show sample of duplicates
    if july_duplicates.sum() > 0:
        sample_date = july_data[july_duplicates]['report_date'].iloc[0]
        sample_campaign = july_data[july_duplicates]['campaign_id'].iloc[0]
        sample_duplicates = july_data[
            (july_data['report_date'] == sample_date) & 
            (july_data['campaign_id'] == sample_campaign)
        ]
        print(f"\nExample duplicate for campaign {sample_campaign} on {sample_date}:")
        print(sample_duplicates[['campaign_id', 'campaign_name', 'cost', 'gross_revenue', 'report_date']])
    
    # Check if the duplicates have identical data
    print("\n--- Checking if duplicates have identical values ---")
    july_grouped = july_data.groupby(['campaign_id', 'report_date'])
    duplicates_with_different_values = 0
    
    for (campaign, date), group in july_grouped:
        if len(group) > 1:
            # Check if all numeric columns have the same values
            numeric_cols = ['cost', 'net_cost', 'orders_(sku)', 'cost_per_order', 'gross_revenue', 'roi']
            for col in numeric_cols:
                if col in group.columns:
                    unique_values = group[col].nunique()
                    if unique_values > 1:
                        duplicates_with_different_values += 1
                        break
    
    print(f"Duplicate groups with different values: {duplicates_with_different_values}")
    
    # Remove duplicates from July data (keep first occurrence)
    july_deduplicated = july_data.drop_duplicates(subset=['campaign_id', 'report_date'], keep='first')
    print(f"\nJuly rows after deduplication: {len(july_deduplicated)}")
    print(f"Rows removed from July: {len(july_data) - len(july_deduplicated)}")
    
    # Calculate the impact
    if 'cost' in july_data.columns and 'gross_revenue' in july_data.columns:
        july_data['cost'] = pd.to_numeric(july_data['cost'], errors='coerce')
        july_data['gross_revenue'] = pd.to_numeric(july_data['gross_revenue'], errors='coerce')
        july_deduplicated['cost'] = pd.to_numeric(july_deduplicated['cost'], errors='coerce')
        july_deduplicated['gross_revenue'] = pd.to_numeric(july_deduplicated['gross_revenue'], errors='coerce')
        
        print(f"\n--- FINANCIAL IMPACT ---")
        print(f"July total cost before deduplication: ${july_data['cost'].sum():.2f}")
        print(f"July total cost after deduplication: ${july_deduplicated['cost'].sum():.2f}")
        print(f"Difference: ${july_data['cost'].sum() - july_deduplicated['cost'].sum():.2f}")
        print(f"\nJuly revenue before deduplication: ${july_data['gross_revenue'].sum():.2f}")
        print(f"July revenue after deduplication: ${july_deduplicated['gross_revenue'].sum():.2f}")
        print(f"Difference: ${july_data['gross_revenue'].sum() - july_deduplicated['gross_revenue'].sum():.2f}")
    
    # Ask for confirmation
    response = input(f"\nDo you want to remove the {len(july_data) - len(july_deduplicated)} duplicate July rows? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\nCombining deduplicated July data with non-July data...")
        
        # Combine deduplicated July with non-July data
        final_df = pd.concat([non_july_data, july_deduplicated], ignore_index=True)
        
        # Sort by date for better organization
        final_df = final_df.sort_values('report_date')
        
        print(f"Final total rows: {len(final_df)}")
        
        # Convert back to original column names for uploading
        original_cols = sh.get_all_values()[0] if sh.get_all_values() else []
        
        # Clear and rewrite the sheet
        print("\nClearing sheet and uploading fixed data...")
        sh.clear()
        
        # Convert datetime columns to string
        for col in final_df.select_dtypes(include=['datetime', 'datetime64[ns]']).columns:
            final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')
        
        # Prepare data for upload
        if original_cols:
            # Map back to original column names
            headers = original_cols
        else:
            headers = final_df.columns.tolist()
        
        data_rows = final_df.astype(str).values.tolist()
        all_data_to_upload = [headers] + data_rows
        
        # Upload fixed data
        sh.update('A1', all_data_to_upload)
        
        print(f"✅ Successfully removed {len(july_data) - len(july_deduplicated)} duplicate July rows!")
        print(f"✅ Sheet now contains {len(final_df)} total rows.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    try:
        fix_july_duplicates()
    except Exception as e:
        print(f"Error: {e}")