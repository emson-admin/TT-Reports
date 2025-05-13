import streamlit as st
import os
from components.data_loader import connect_to_google_sheets, load_data
from components.sidebar_filters import render_sidebar_filters
from components.file_uploader import render_file_uploader
from components.dashboard import render_dashboard, render_historical_data_view
from components.data_export import render_export_section
from services.email_service import send_weekly_email_data
from utils.helpers import extract_account

# Set page configuration
st.set_page_config(layout="wide")

# Main application logic
def run_main_app():
    """Main application logic that orchestrates components."""
    
    # Connect to Google Sheets
    sheet = connect_to_google_sheets(st.secrets)
    
    # App title
    st.title('📈 Weekly Ad Report Uploader')

    # Clear file uploader if needed (after upload completes)
    if st.session_state.get("clear_uploader"):
        st.session_state.pop("uploader", None)
        st.session_state["clear_uploader"] = False

    # File uploader for admin users
    if st.session_state.get("is_admin"):
        render_file_uploader(sheet)
    
    # Load data from Google Sheets
    data = load_data(sheet)

    # Check for report_date column
    if 'report_date' not in data.columns or data['report_date'].isnull().all():
        st.error("❌ The 'report_date' column is missing or contains no valid dates. Double-check the upload formatting.")
        st.stop()

    # Handle account_name column for backward compatibility
    if data.empty:
        data['campaign_name'] = pd.Series(dtype='object')
        data['account_name'] = pd.Series(dtype='object')
    elif 'account_name' not in data.columns:
        st.sidebar.info("Deriving 'account_name' for older data or missing column.")
        if 'campaign_name' in data.columns:
            data['account_name'] = data['campaign_name'].apply(extract_account)
        else:
            data['account_name'] = pd.Series(["Other Accounts"] * len(data), index=data.index)

    # Render sidebar filters
    filter_options = render_sidebar_filters(data)
    
    # Render dashboard with filtered data
    filtered_data = render_dashboard(data, filter_options, sheet)
    
    # If no data after filtering, stop here
    if filtered_data.empty:
        st.info("No data available to display. Please upload reports or check Google Sheet.")
        st.stop()
    
    # Export data section
    export_data = render_export_section(filtered_data)
    
    # Email data section for admins
    if st.session_state.get("is_admin"):
        send_weekly_email_data(filtered_data, export_data, st.secrets)
    
    # Historical data view
    render_historical_data_view(sheet)

# Authentication handling
def handle_authentication():
    """Handle user authentication."""
    ENABLE_AUTH = os.getenv("STREAMLIT_ENABLE_AUTH", "false").lower() == "true"

    if not ENABLE_AUTH:
        # Authentication is disabled, grant full access by default for local development
        if "authenticated" not in st.session_state:  # Initialize if not already set by a previous run
            st.session_state.authenticated = True
            st.session_state.is_admin = True
        st.sidebar.info("🔑 Authentication Disabled (Dev Mode)")
        run_main_app()
    else:
        # Authentication is enabled
        if "authenticated" not in st.session_state:
            st.title("🔒 Protected Dashboard")
            with st.form("auth_form"):
                pw = st.text_input("Enter viewer password", type="password")
                admin_key = st.text_input("Enter admin key (optional)", type="password")
                submitted = st.form_submit_button("Login")

            if submitted:
                if pw == st.secrets["app_password"]:
                    st.session_state.authenticated = True
                    st.session_state.is_admin = admin_key == st.secrets["admin_key"]
                    st.rerun()
                else:
                    st.error("Incorrect password")
            st.stop()  # Stop execution if login form is shown and not successfully submitted

        # If we reach here, authentication is enabled AND user is authenticated.
        render_auth_sidebar()
        run_main_app()

def render_auth_sidebar():
    """Render authentication-related sidebar elements."""
    with st.sidebar:
        if st.button("🔒 Logout"):
            if "authenticated" in st.session_state:
                del st.session_state.authenticated
            if "is_admin" in st.session_state:
                del st.session_state.is_admin
            st.rerun()

        # Allow non-admins to enter admin key later (only if auth is enabled)
        if "is_admin" not in st.session_state:  # Should be set by login, but as a safeguard
            st.session_state.is_admin = False
            
        if st.session_state.authenticated and not st.session_state.is_admin:
            with st.expander("🔑 Admin Access"):
                with st.form("admin_key_form"):
                    admin_key_input = st.text_input("Enter admin key to enable uploads", type="password")
                    admin_key_submitted = st.form_submit_button("Unlock Admin Features")

                if admin_key_submitted:
                    if admin_key_input == st.secrets["admin_key"]:
                        st.session_state.is_admin = True
                        st.sidebar.success("Admin features unlocked!")
                        st.rerun()
                    elif admin_key_input:  # if a key was entered but it's wrong
                        st.sidebar.error("Incorrect admin key.")

# Entry point for the application
if __name__ == "__main__":
    import pandas as pd  # Add this import for data handling in this file
    handle_authentication()
