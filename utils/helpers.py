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
    
    return "Other Accounts"