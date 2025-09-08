import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

def analyze_july_data():
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
    
    # Show available columns
    print(f"\nAvailable columns: {df.columns.tolist()}")
    
    # Normalize column names
    df.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in df.columns])
    
    # Convert report_date to datetime
    if 'report_date' in df.columns:
        df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')
    
    # Filter July data
    july_data = df[df['report_date'].dt.month == 7]
    
    print(f"\n=== JULY DATA ANALYSIS ===")
    print(f"Total rows in July: {len(july_data)}")
    print(f"Unique dates in July: {july_data['report_date'].nunique()}")
    print(f"Date range: {july_data['report_date'].min()} to {july_data['report_date'].max()}")
    
    # Check for exact duplicates in July
    july_duplicates = july_data[july_data.duplicated(keep=False)]
    print(f"\n--- DUPLICATE ANALYSIS ---")
    print(f"Exact duplicate rows in July: {len(july_duplicates)}")
    
    # Check for duplicates by key fields
    if 'campaign_id' in df.columns:
        july_key_duplicates = july_data[july_data.duplicated(subset=['campaign_id', 'report_date'], keep=False)]
        print(f"Rows with duplicate (campaign_id + report_date) in July: {len(july_key_duplicates)}")
        
        if len(july_key_duplicates) > 0:
            print("\nDuplicate campaigns by date:")
            dup_summary = july_key_duplicates.groupby(['report_date', 'campaign_id']).size().reset_index(name='count')
            dup_summary = dup_summary[dup_summary['count'] > 1].sort_values('count', ascending=False)
            print(dup_summary.head(20))
    
    # Convert numeric columns
    numeric_cols = ['cost', 'gross_revenue', 'orders_(sku)', 'impressions', 'clicks']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Monthly comparison
    print(f"\n--- MONTHLY COMPARISON ---")
    agg_dict = {}
    if 'cost' in df.columns:
        agg_dict['cost'] = 'sum'
    if 'gross_revenue' in df.columns:
        agg_dict['gross_revenue'] = 'sum'
    agg_dict['report_date'] = 'count'
    
    monthly_stats = df.groupby(df['report_date'].dt.to_period('M')).agg(agg_dict).rename(columns={'report_date': 'row_count'})
    
    print("\nMonthly totals:")
    print(monthly_stats)
    
    # Calculate average daily spend for each month
    print(f"\n--- DAILY AVERAGES ---")
    if 'cost' in df.columns and 'gross_revenue' in df.columns:
        daily_avg = df.groupby(df['report_date'].dt.to_period('M')).apply(
            lambda x: pd.Series({
                'avg_daily_cost': x.groupby('report_date')['cost'].sum().mean() if 'cost' in x.columns else 0,
                'avg_daily_revenue': x.groupby('report_date')['gross_revenue'].sum().mean() if 'gross_revenue' in x.columns else 0,
                'days_with_data': x['report_date'].nunique(),
                'avg_rows_per_day': len(x) / x['report_date'].nunique() if x['report_date'].nunique() > 0 else 0
            })
        )
        print(daily_avg)
    
    # Check July daily data for anomalies
    print(f"\n--- JULY DAILY BREAKDOWN ---")
    if 'cost' in july_data.columns and 'gross_revenue' in july_data.columns:
        july_daily = july_data.groupby('report_date').agg({
            'cost': ['sum', 'count'],
            'gross_revenue': 'sum'
        }).round(2)
        july_daily.columns = ['daily_cost', 'campaign_count', 'daily_revenue']
        print(july_daily)
    else:
        print("Cost or revenue columns not found")
    
    # Check for dates that appear twice as much
    print(f"\n--- CHECKING FOR DOUBLE DATA ---")
    if 'cost' in july_data.columns and 'gross_revenue' in july_data.columns:
        july_daily = july_data.groupby('report_date')['cost'].sum()
        if len(july_daily) > 0:
            avg_daily_cost = july_daily.median()
            high_cost_days = july_daily[july_daily > avg_daily_cost * 1.8]
            if len(high_cost_days) > 0:
                print(f"Days with unusually high costs (>1.8x median of ${avg_daily_cost:.2f}):")
                for date, cost in high_cost_days.items():
                    print(f"  {date}: ${cost:.2f}")
        else:
            print("No daily data to analyze")
    
    # Check account distribution in July
    if 'account_name' in df.columns:
        print(f"\n--- JULY ACCOUNT DISTRIBUTION ---")
        july_accounts = july_data.groupby('account_name').agg({
            'cost': 'sum',
            'report_date': 'nunique'
        }).rename(columns={'report_date': 'days_active'})
        print(july_accounts)
    
    return df, july_data

if __name__ == "__main__":
    try:
        df, july_data = analyze_july_data()
    except Exception as e:
        print(f"Error: {e}")