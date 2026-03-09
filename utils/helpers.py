import pandas as pd
import re
import io
import os
import uuid
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill

def extract_account(campaign_name):
    """
    Extracts account name from campaign name using pattern matching.
    """
    if pd.isna(campaign_name):
        return "Other Accounts"

    campaign_name_lower = str(campaign_name).lower()

    if "granitestone" in campaign_name_lower:
        return "Granitestone"
    elif "bell and howell" in campaign_name_lower:
        return "Bell+Howell"
    elif "gotham steel" in campaign_name_lower:
        return "Gotham Steel"

    return "Other Accounts"

def detect_missing_dates(data):
    """
    Detects missing dates in the report data for each account.
    Returns a dictionary with account names as keys and lists of missing dates as values.
    """
    if data.empty or 'account_name' not in data.columns or 'report_date' not in data.columns:
        return {}

    # Ensure report_date is datetime
    data = data.copy()
    data['report_date'] = pd.to_datetime(data['report_date'], errors='coerce')

    # Drop rows with invalid dates
    data = data.dropna(subset=['report_date'])

    if data.empty:
        return {}

    missing_dates_by_account = {}

    # Group by account and check for missing dates
    for account_name in data['account_name'].unique():
        account_data = data[data['account_name'] == account_name]

        if len(account_data) < 2:
            # Need at least 2 dates to detect gaps
            continue

        # Get min and max dates for this account
        min_date = account_data['report_date'].min()
        max_date = account_data['report_date'].max()

        # Create a complete date range
        date_range = pd.date_range(start=min_date, end=max_date, freq='D')

        # Find actual dates in the data
        actual_dates = set(account_data['report_date'].dt.date)

        # Find missing dates
        missing_dates = [date.date() for date in date_range if date.date() not in actual_dates]

        if missing_dates:
            missing_dates_by_account[account_name] = missing_dates

    return missing_dates_by_account