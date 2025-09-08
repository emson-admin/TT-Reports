import streamlit as st
import pandas as pd
from utils.helpers import extract_account
from datetime import date, timedelta # Added for date calculations

def render_sidebar_filters(data):
    """Render all sidebar filters and return the selected values."""
    st.sidebar.markdown("### 🔍 Filter Options")
    
    from components.data_loader import get_date_range_values
    min_date_val, max_date_val = get_date_range_values(data)
    today = date.today()

    # Initialize session state for date range, ensuring they are within current data bounds
    if 'start_date' not in st.session_state or st.session_state.start_date is None:
        st.session_state.start_date = min_date_val
    else:
        # Ensure start_date is within the global min/max bounds
        st.session_state.start_date = max(st.session_state.start_date, min_date_val)
        st.session_state.start_date = min(st.session_state.start_date, max_date_val)

    if 'end_date' not in st.session_state or st.session_state.end_date is None:
        st.session_state.end_date = max_date_val
    else:
        # Ensure end_date is within the global min/max bounds
        st.session_state.end_date = min(st.session_state.end_date, max_date_val)
        st.session_state.end_date = max(st.session_state.end_date, min_date_val)

    # Ensure start_date is not after end_date
    if st.session_state.start_date > st.session_state.end_date:
        st.session_state.start_date = st.session_state.end_date # Adjust start_date to be same as end_date

    quick_options = [
        "Custom Range", "Yesterday", "Previous Week", "Last 7 Days", "Last 14 Days",
        "Current Month to Date", "Previous Month", "Last 90 Days", "All-Time"
    ]

    # Callback for when date_input is manually changed
    def on_date_input_change():
        date_value_from_widget = st.session_state.report_date_range_input_key
        
        # Ensure the value from the date_input widget is a 2-element tuple.
        # If not (e.g., if it's a 1-tuple as the error suggests, or None, or not a tuple),
        # then the selection process is incomplete or the widget state is unexpected.
        # In such cases, we return early to prevent errors and wait for a valid 2-tuple.
        if not (isinstance(date_value_from_widget, tuple) and len(date_value_from_widget) == 2):
            return

        new_start, new_end = date_value_from_widget

        # Proceed to update session state only if both dates are selected (i.e., not None).
        # If one or both are None, it means the user is still in the process of selecting
        # the range or has cleared one/both dates in the widget. We don't want to
        # update our main start_date/end_date session variables with None values
        # or reflect an incomplete range as "Custom Range" prematurely.
        if new_start is not None and new_end is not None:
            # Ensure chronological order for the dates stored in session state.
            if new_start > new_end:
                st.session_state.start_date = new_end
                st.session_state.end_date = new_start
            else:
                st.session_state.start_date = new_start
                st.session_state.end_date = new_end
            
            # If the dates were successfully updated via the date_input widget,
            # then the selection is now a "Custom Range".
            st.session_state.quick_date_preset_selector = "Custom Range"

    # Callback for when quick_date_preset_selector changes
    def on_quick_select_change():
        preset = st.session_state.quick_date_preset_selector
        
        # These are captured from the outer scope of render_sidebar_filters
        # today, min_date_val, max_date_val

        if preset == "Yesterday":
            st.session_state.start_date = today - timedelta(days=1)
            st.session_state.end_date = today - timedelta(days=1)
        elif preset == "Previous Week":
            # Calculate previous week (Monday to Sunday)
            # Get the most recent Monday
            days_since_monday = today.weekday()  # Monday is 0, Sunday is 6
            last_monday = today - timedelta(days=days_since_monday)
            # Previous week's Monday is 7 days before
            prev_week_monday = last_monday - timedelta(days=7)
            # Previous week's Sunday is 6 days after that Monday
            prev_week_sunday = prev_week_monday + timedelta(days=6)
            st.session_state.start_date = prev_week_monday
            st.session_state.end_date = prev_week_sunday
        elif preset == "Last 7 Days":
            st.session_state.start_date = today - timedelta(days=6)
            st.session_state.end_date = today
        elif preset == "Last 14 Days":
            st.session_state.start_date = today - timedelta(days=13)
            st.session_state.end_date = today
        elif preset == "Current Month to Date":
            st.session_state.start_date = today.replace(day=1)
            st.session_state.end_date = today
        elif preset == "Previous Month":
            first_day_current_month = today.replace(day=1)
            last_day_previous_month = first_day_current_month - timedelta(days=1)
            first_day_previous_month = last_day_previous_month.replace(day=1)
            st.session_state.start_date = first_day_previous_month
            st.session_state.end_date = last_day_previous_month
        elif preset == "Last 90 Days":
            st.session_state.start_date = today - timedelta(days=89)
            st.session_state.end_date = today
        elif preset == "All-Time":
            st.session_state.start_date = min_date_val
            st.session_state.end_date = max_date_val
        # If "Custom Range" is selected, no date changes are made here;
        # the date_input widget remains the source of truth for custom dates.

    # Determine the initial index for the selectbox based on session state
    # Default to "Custom Range" if the specific preset is not found or not set
    try:
        current_preset_index = quick_options.index(st.session_state.get('quick_date_preset_selector', "Custom Range"))
    except ValueError:
        current_preset_index = 0 # Default to "Custom Range"

    st.sidebar.selectbox(
        "Quick Date Range",
        options=quick_options,
        key='quick_date_preset_selector',
        on_change=on_quick_select_change,
        index=current_preset_index
    )
    
    # Date Range Filter input field
    # Its value is driven by session state, which can be updated by the selectbox or manual input.
    st.sidebar.date_input(
        "Report Date Range", # Label for the date_input
        value=(st.session_state.start_date, st.session_state.end_date),
        min_value=min_date_val,
        max_value=max_date_val,
        key='report_date_range_input_key', # Key to access its value and for on_change
        on_change=on_date_input_change
    )
    
    final_date_range = (st.session_state.start_date, st.session_state.end_date)
    
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
        "date_range": final_date_range, # Use the session state managed date range
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