import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

def connect_to_google_sheets(secrets):
    """Connect to Google Sheets and return the worksheet."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(secrets["gcp"], scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('TikTok GMVMAX Ad Reports').worksheet('Data')
    return sh

@st.cache_data(ttl=0)
def load_data(_sheet):
    """
    Load data from Google Sheet and perform necessary conversions.
    
    Args:
        _sheet: The Google Sheet worksheet object (with leading underscore to prevent hashing)
        
    Returns:
        DataFrame with properly formatted columns
    """
    df = pd.DataFrame(_sheet.get_all_records())
    if not df.empty:
        # Normalize column names
        df.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in df.columns])
        
        # Define columns that should be numeric
        cols_to_convert_to_numeric = [
            'cost', 'gross_revenue', 'orders_(sku)', 'roi', 'cost_per_order',
            'impressions', 'clicks', 'ctr', 'cpc', 'cpm', 'net_cost'
        ]
        
        for col in cols_to_convert_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert report_date to datetime
        if 'report_date' in df.columns:
            df['report_date'] = pd.to_datetime(df['report_date'], errors='coerce')

    return df

def get_date_range_values(data):
    """Get min and max dates from data for date range picker defaults."""
    if not data.empty and 'report_date' in data.columns:
        min_date_val = data['report_date'].min().date()
        max_date_val = data['report_date'].max().date()
    else:
        min_date_val = datetime.today() - timedelta(days=7)
        max_date_val = datetime.today()
    
    return min_date_val, max_date_val