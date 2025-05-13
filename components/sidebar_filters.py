import streamlit as st
import pandas as pd
from utils.helpers import extract_account

def render_sidebar_filters(data):
    """Render all sidebar filters and return the selected values."""
    st.sidebar.markdown("### 🔍 Filter Options")
    
    from components.data_loader import get_date_range_values
    min_date_val, max_date_val = get_date_range_values(data)
    
    # Date Range Filter
    date_range = st.sidebar.date_input("Report Date Range", value=(min_date_val, max_date_val))
    
    # Account Filter
    selected_accounts = []
    if not data.empty and 'account_name' in data.columns:
        unique_accounts = [str(acc) for acc in data['account_name'].unique().tolist()]
        account_options = ["All Accounts"] + sorted(unique_accounts)
        selected_accounts = st.sidebar.multiselect("Account(s)", account_options, default=[])
    
    # Campaign Filter with Select All functionality
    selected_campaigns = render_campaign_filter(data, selected_accounts)
    
    # Metric selection
    numeric_columns = data.select_dtypes(include='number').columns.tolist()
    
    # Define desired default metrics
    desired_default_main_metrics = ["gross_revenue"]
    desired_default_side_metrics = ["orders_(sku)", "cost_per_order", "cost", "roi"]

    # Filter defaults to only include available numeric columns
    actual_default_main_metrics = [m for m in desired_default_main_metrics if m in numeric_columns]
    actual_default_side_metrics = [m for m in desired_default_side_metrics if m in numeric_columns]
    
    main_metrics = st.sidebar.multiselect(
        "📈 Main Graph & KPI Metrics",
        options=numeric_columns,
        default=actual_default_main_metrics
    )

    side_metrics = st.sidebar.multiselect(
        "📊 Side-by-Side Metric Charts",
        options=numeric_columns,
        default=actual_default_side_metrics
    )
    
    return {
        "date_range": date_range,
        "selected_accounts": selected_accounts,
        "selected_campaigns": selected_campaigns,
        "main_metrics": main_metrics,
        "side_metrics": side_metrics
    }

def render_campaign_filter(data, selected_accounts):
    """Render campaign filter with Select All functionality."""
    campaign_options_for_multiselect = []
    
    if not data.empty and 'campaign_name' in data.columns:
        data_for_campaign_options = data
        
        if selected_accounts and "All Accounts" not in selected_accounts:
            if 'account_name' in data.columns:
                data_for_campaign_options = data[data['account_name'].isin(selected_accounts)]
            else:
                data_for_campaign_options = pd.DataFrame(columns=data.columns)
        
        if not data_for_campaign_options.empty:
            unique_campaigns_list = data_for_campaign_options['campaign_name'].unique().tolist()
            campaign_options_for_multiselect = sorted([
                str(c) for c in unique_campaigns_list if pd.notna(c) and str(c).strip()
            ])
    
    if data.empty and ('campaign_name' not in data.columns or not campaign_options_for_multiselect):
        st.sidebar.info("No data loaded to determine campaigns for filtering.")
    
    # Initialize session state for selected campaigns
    if 'selected_campaigns_key' not in st.session_state:
        st.session_state.selected_campaigns_key = []
    
    if campaign_options_for_multiselect:
        # Callback for the "Select All" checkbox
        def on_toggle_select_all_campaigns():
            if st.session_state.get('select_all_campaigns_checkbox_key', False):
                st.session_state.selected_campaigns_key = campaign_options_for_multiselect[:]
            else:
                st.session_state.selected_campaigns_key = []
        
        # Determine if all are currently selected
        all_currently_selected = False
        if campaign_options_for_multiselect:
            if set(st.session_state.get('selected_campaigns_key', [])) == set(campaign_options_for_multiselect):
                all_currently_selected = True
        
        st.sidebar.checkbox(
            "Select/Deselect All Campaigns",
            value=all_currently_selected,
            key='select_all_campaigns_checkbox_key',
            on_change=on_toggle_select_all_campaigns,
            help="Toggle to select or deselect all campaigns currently available in the list below."
        )
    
    selected_campaigns = st.sidebar.multiselect(
        "Campaign(s)",
        options=campaign_options_for_multiselect,
        key='selected_campaigns_key'
    )
    
    return selected_campaigns