import streamlit as st
import pandas as pd
import datetime
import gspread
import re
import io
from google.oauth2.service_account import Credentials
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill
from google.cloud import storage
import uuid
import requests
import altair as alt # Moved import altair to top
import os

#page layout
st.set_page_config(layout="wide")

# --- Helper Functions ---
def upload_excel_to_gcs(excel_bytes, bucket_name, credentials_dict, original_filename="report.xlsx"):
    """Uploads an Excel file (in bytes) to Google Cloud Storage."""
    try:
        buffer = io.BytesIO(excel_bytes)
        buffer.seek(0)

        # Create a unique filename, perhaps incorporating the original name
        base, ext = os.path.splitext(original_filename)
        filename = f"reports/{base}_{uuid.uuid4().hex}{ext}"

        # Init GCS client
        client = storage.Client.from_service_account_info(credentials_dict)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Construct the public URL manually for uniform bucket-level access
        public_url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
        return public_url
    except Exception as e:
        st.error(f"Error uploading Excel to GCS: {e}")
        return None

def upload_chart_to_gcs(chart, bucket_name, credentials_dict):
    """Uploads an Altair chart image to Google Cloud Storage."""
    try:
        # Convert chart to PNG in memory
        buffer = io.BytesIO()
        # Ensure chart object is valid before saving
        if chart is None:
            st.error("Chart object is None, cannot upload.")
            return None
        chart.save(buffer, format='png', scale_factor=2.0)
        buffer.seek(0)

        # Create a unique filename
        filename = f"charts/chart_{uuid.uuid4().hex}.png"

        # Init GCS client
        client = storage.Client.from_service_account_info(credentials_dict)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(buffer, content_type='image/png')

        # Make it publicly accessible - REMOVED due to Uniform Bucket-Level Access
        # blob.make_public() 
        
        # Construct the public URL manually for uniform bucket-level access
        # This assumes the bucket is configured for public read access in GCP IAM.
        public_url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
        return public_url
    except Exception as e:
        st.error(f"Error uploading chart to GCS: {e}")
        return None

def generate_specific_metric_chart(chart_df, metric_col_name, display_metric_name, date_col='report_date', campaign_col='campaign_name'):
    """Generates an Altair chart for a single metric using pre-aggregated data."""
    if metric_col_name not in chart_df.columns:
        st.warning(f"Metric column '{metric_col_name}' not found in chart data for '{display_metric_name}'.")
        return None
    
    chart = alt.Chart(chart_df).mark_line(point=True).encode(
        x=alt.X(f'{date_col}:T', title='Date'),
        y=alt.Y(f'{metric_col_name}:Q', title=display_metric_name.replace("_", " ").title(), scale=alt.Scale(zero=True)),
        color=alt.Color(f'{campaign_col}:N', legend=alt.Legend(title="Campaign")),
        tooltip=[
            alt.Tooltip(f'{date_col}:T', title="Date"),
            alt.Tooltip(f'{campaign_col}:N', title="Campaign"),
            alt.Tooltip(f'{metric_col_name}:Q', title=display_metric_name.replace("_", " ").title(), format=",.2f")
        ]
    ).properties(
        width=600,
        height=300,
        title=f"{display_metric_name.replace('_', ' ').title()} Over Time"
    ).interactive()
    return chart

# --- Main Application Logic ---
def run_main_app():
    # Connect to Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_info(st.secrets["gcp"], scopes=scope)
    gc = gspread.authorize(credentials)
    sh = gc.open('TikTok GMVMAX Ad Reports').worksheet('Data')

    st.title('📈 Weekly Ad Report Uploader')

    # If flag is set, clear uploader state by resetting its key
    if st.session_state.get("clear_uploader"):
        st.session_state.pop("uploader", None)
        st.session_state["clear_uploader"] = False

    # File uploader
    if st.session_state.get("is_admin"):
        st.markdown("## 🔼 Upload Daily Reports")
        uploaded_files = st.file_uploader(
            "📂 Upload one or more daily ad reports (.xlsx)",
            type="xlsx",
            accept_multiple_files=True,
            key="uploader"
        )

        # Define all_data globally so it's always initialized
        all_data = []
        if uploaded_files:

            for file in uploaded_files:
                try:
                    df = pd.read_excel(file)

                    # Clean & normalize
                    df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
                    
                    # Parse date from filename
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", file.name)
                    if date_match:
                        report_date = pd.to_datetime(date_match.group())
                        df['report_date'] = report_date
                    else:
                        st.warning(f"⚠️ Could not find date in: {file.name}")
                        continue

                    # Remove zero-spend rows
                    if 'cost' in df.columns:
                        df = df[df['cost'].fillna(0) > 0]

                    # Convert campaign_id to string
                    if 'campaign_id' in df.columns:
                        df['campaign_id'] = df['campaign_id'].apply(lambda x: f"'{x}")

                    df['upload_date'] = datetime.datetime.now().strftime('%Y-%m-%d')

                    all_data.append(df)

                except Exception as e:
                    st.error(f"❌ Error processing {file.name}: {e}")

            if all_data and st.button("✅ Upload All to Google Sheets"):

                # Combine uploaded data into one DataFrame
                combined_df = pd.concat(all_data, ignore_index=True)

                # Load existing data from sheet
                existing = pd.DataFrame(sh.get_all_records())
                existing.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in existing.columns])

                # Ensure combined_df['report_date'] exists and is datetime
                combined_df['report_date'] = pd.to_datetime(combined_df['report_date'])
                if not existing.empty and 'report_date' in existing.columns:
                    existing['report_date'] = pd.to_datetime(existing['report_date'])

                    # Normalize campaign_id columns for reliable joins
                    if 'campaign_id' in combined_df.columns and 'campaign_id' in existing.columns:
                        existing['campaign_id'] = existing['campaign_id'].astype(str).str.strip()
                        combined_df['campaign_id'] = combined_df['campaign_id'].astype(str).str.strip()

                        # Find rows that would be duplicates (same campaign_id + report_date)
                        duplicate_rows = pd.merge(
                            combined_df,
                            existing[['campaign_id', 'report_date']],
                            on=['campaign_id', 'report_date'],
                            how='inner'
                        )

                        # If duplicates exist, let user choose whether to skip or overwrite them
                        if not duplicate_rows.empty:
                            with st.expander("⚠️ Duplicate Rows Detected"):
                                st.dataframe(duplicate_rows)

                            # Ask user whether to overwrite or skip duplicate rows
                            overwrite = st.radio(
                                "⚠️ Duplicate rows detected based on 'campaign_id' and 'report_date'. What would you like to do?",
                                ("Skip duplicates", "Overwrite duplicates")
                            )

                            if overwrite == "Overwrite duplicates":
                                # Remove duplicates from the existing sheet data
                                existing = existing.merge(
                                    duplicate_rows[['campaign_id', 'report_date']],
                                    on=['campaign_id', 'report_date'],
                                    how='left',
                                    indicator=True
                                ).query('_merge == "left_only"').drop(columns=['_merge'])

                                # Final data is: cleaned existing rows + all uploaded rows (including overwrites)
                                final_df = pd.concat([existing, combined_df], ignore_index=True)
                                st.info(f"✅ Overwrote {len(duplicate_rows)} existing rows.")
                            else:
                                # Skip: remove duplicate rows from the upload
                                final_df = pd.merge(
                                    combined_df,
                                    duplicate_rows[['campaign_id', 'report_date']],
                                    on=['campaign_id', 'report_date'],
                                    how='left',
                                    indicator=True
                                ).query('_merge == "left_only"').drop(columns(['_merge']))
                                st.info(f"✅ Skipped {len(duplicate_rows)} duplicate rows.")
                        else:
                            # No duplicates: just combine everything
                            final_df = pd.concat([existing, combined_df], ignore_index=True)
                    else:
                        # Fallback if campaign_id missing: dedupe just by date
                        final_df = combined_df[~combined_df['report_date'].isin(existing['report_date'])]
                        final_df = pd.concat([existing, final_df], ignore_index=True)
                        st.info(f"⚠️ No 'campaign_id' column found. Deduped only by date.")
                else:
                    # No existing data at all — treat this as the first upload
                    final_df = combined_df.copy()
                    st.info("ℹ️ No existing data found. Treating this as a fresh upload.")


            # Get current sheet row count to determine where to append
            existing_records = sh.get_all_values()
            is_first_upload = len(existing_records) == 0

            # Convert any datetime columns to string format for JSON compatibility with gspread
            for col in final_df.select_dtypes(include=['datetime', 'datetime64[ns]']):
                final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')


            # Build the upload payload
            rows_to_upload = (
                [final_df.columns.tolist()] + final_df.astype(str).values.tolist()
                if is_first_upload else final_df.astype(str).values.tolist()
            )


            # Determine next row to write to
            next_row = len(existing_records) + 1

            # Upload to Google Sheet
            sh.update(f'A{next_row}', rows_to_upload)

            # Show success and rerun app to reflect updated data
            st.success(f'🎉 Uploaded {len(uploaded_files)} file(s) successfully!')
            st.toast("Upload complete!", icon="✅")
            # Clear uploader input by resetting session state
            st.session_state["clear_uploader"] = True
            st.rerun()
            
    @st.cache_data(ttl=300)
    def load_data():
        df = pd.DataFrame(sh.get_all_records())
        if not df.empty:
            df.columns = pd.Index([str(col).strip().lower().replace(" ", "_") for col in df.columns])
        return df

    # Load data from Google Sheets
    data = load_data()

    # Make sure report_date is datetime
    if 'report_date' not in data.columns:
        st.error("❌ The 'report_date' column is missing. Double-check the upload formatting.")
        st.stop()

    data['report_date'] = pd.to_datetime(data['report_date'])

    with st.sidebar:
        st.markdown("### 🔍 Filter Options")

        min_date = data['report_date'].min().date()
        max_date = data['report_date'].max().date()
        date_range = st.date_input("Report Date Range", value=(min_date, max_date))

        campaign_options = sorted(data['campaign_name'].unique())
        selected_campaigns = st.multiselect("Campaign(s)", campaign_options, default=campaign_options)

        numeric_columns = data.select_dtypes(include='number').columns.tolist()
        main_metrics = st.multiselect(
        "📈 Main Graph & KPI Metrics",
        options=numeric_columns,
        default=["cost", "gross_revenue", "roi"]
        )

        side_metrics = st.multiselect(
            "📊 Side-by-Side Metric Charts",
            options=numeric_columns,
            default=["orders_(sku)", "cost_per_order"]
        )


    # Filter data
    filtered_data = data[
        (data['report_date'] >= pd.to_datetime(date_range[0])) &
        (data['report_date'] <= pd.to_datetime(date_range[1])) &
        (data['campaign_name'].isin(selected_campaigns))
    ]

    # Group for chart
    if not filtered_data.empty and main_metrics:
        grouped = (
            filtered_data[['report_date', 'campaign_name'] + main_metrics]
            .groupby(['report_date', 'campaign_name'])
            .sum()
            .reset_index()
        )

        melted = grouped.melt(
            id_vars=['report_date', 'campaign_name'],
            value_vars=main_metrics,
            var_name='Metric',
            value_name='Value'
        )

        line_chart = alt.Chart(melted).mark_line(point=True).encode(
            x='report_date:T',
            y='Value:Q',
            color=alt.Color('campaign_name:N', legend=alt.Legend(title="Campaign")),
            strokeDash='Metric:N',
            tooltip=['report_date:T', 'campaign_name:N', 'Metric:N', 'Value:Q']
        ).properties(
            width=900,
            height=450,
            title="📈 Campaign Performance Over Time"
        ).interactive()

        st.altair_chart(line_chart, use_container_width=True)


    # Side-by-side metric charts (wider layout for full screen)
    if not filtered_data.empty and side_metrics:
        st.subheader("📊 Side-by-Side Metric Charts by Campaign")

        # Break metrics into chunks of 2 per row for better visual spacing
        metric_chunks = [side_metrics[i:i+2] for i in range(0, len(side_metrics), 2)]

        for chunk in metric_chunks:
            cols = st.columns(len(chunk))  # 2-column layout
            for i, metric in enumerate(chunk):
                with cols[i]:
                    chart_data = (
                        filtered_data[['report_date', 'campaign_name', metric]]
                        .groupby(['report_date', 'campaign_name'])
                        .sum()
                        .reset_index()
                    )

                    chart = alt.Chart(chart_data).mark_line(point=True).encode(
                        x=alt.X('report_date:T', title=''),
                        y=alt.Y(metric, title=metric.replace("_", " ").title(), scale=alt.Scale(zero=True)),
                        color=alt.Color('campaign_name:N', legend=None),
                        tooltip=[
                            alt.Tooltip('report_date:T', title="Date"),
                            alt.Tooltip('campaign_name:N', title="Campaign"),
                            alt.Tooltip(metric, title=metric.replace("_", " ").title(), format=",.2f")
                        ]
                    ).properties(
                        width=600,  # ← wider width
                        height=300,
                        title=metric.replace("_", " ").title()
                    )

                    st.altair_chart(chart, use_container_width=False)

    # KPI Summary
    st.subheader("📌 Summary Metrics")

    if not filtered_data.empty:
        total_cost = filtered_data['cost'].sum()
        total_revenue = filtered_data['gross_revenue'].sum()
        total_orders = filtered_data['orders_(sku)'].sum()
        avg_roi = filtered_data['roi'].mean()
        avg_cpo = filtered_data['cost_per_order'].mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Cost", f"${total_cost:,.2f}")
        col2.metric("📈 Gross Revenue", f"${total_revenue:,.2f}")
        col3.metric("📊 Avg ROI", f"{avg_roi:.2f}x")

        col4, col5 = st.columns(2)
        col4.metric("📦 Total Orders", f"{int(total_orders):,}")
        col5.metric("🧾 Avg Cost/Order", f"${avg_cpo:,.2f}")

    else:
        st.info("No data to summarize for the current filter selection.")

    # 📤 Export Filtered Data to Excel File
    st.subheader("📤 Export Report")

    if not filtered_data.empty:
        export_granularity = st.selectbox(
            "🗂 Grouping for Export",
            options=["Daily", "Weekly", "Monthly"],
            index=1,
            help="Aggregate data by day, week (Monday start), or calendar month"
        )

        # Ensure datetime
        filtered_data['report_date'] = pd.to_datetime(filtered_data['report_date'])

        # Assign period
        if export_granularity == "Weekly":
            filtered_data['period'] = filtered_data['report_date'].dt.to_period("W").apply(lambda r: r.start_time)
        elif export_granularity == "Monthly":
            filtered_data['period'] = filtered_data['report_date'].dt.to_period("M").apply(lambda r: r.start_time)
        else:
            filtered_data['period'] = filtered_data['report_date'].dt.date

        # Aggregate numeric data by campaign + period
        numeric_columns = filtered_data.select_dtypes(include='number').columns.tolist()
        summary_df = (
            filtered_data
            .groupby(['campaign_name', 'period'])[numeric_columns]
            .sum()
            .reset_index()
        )

        # Recalculate ROI and Cost/Order
        summary_df['roi'] = summary_df['gross_revenue'] / summary_df['cost']
        summary_df['cost_per_order'] = summary_df['cost'] / summary_df['orders_(sku)']

        # Replace infinite or undefined values
        summary_df.replace([float('inf'), -float('inf')], pd.NA, inplace=True)
        summary_df['roi'] = summary_df['roi'].fillna(0).round(2)
        summary_df['cost_per_order'] = summary_df['cost_per_order'].fillna(0).round(2)
        summary_df['period'] = pd.to_datetime(summary_df['period']).dt.strftime('%Y-%m-%d')


        # Export to Excel (one sheet per campaign)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for campaign_name, campaign_data in summary_df.groupby('campaign_name'):
                sheet_name = campaign_name[:31]
                campaign_data.to_excel(writer, index=False, sheet_name=sheet_name)

                # Get worksheet and auto-adjust column widths
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]

                # ✅ Freeze header row
                worksheet.freeze_panes = worksheet["A2"]

                # Highlight headers with light green
                header_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                for cell in worksheet[1]:  # Row 1
                    cell.fill = header_fill

                 # ✅ Auto-adjust column widths
                for i, column in enumerate(campaign_data.columns, 1):  # 1-indexed
                    if column == "period":
                        max_length = 20  # wider default for date strings
                    else:
                        max_length = max(
                            campaign_data[column].astype(str).map(len).max(),
                            len(column)
                        ) + 2
                    col_letter = get_column_letter(i)
                    worksheet.column_dimensions[col_letter].width = max_length


        # Download button
        start_str = date_range[0].strftime("%Y-%m-%d")
        end_str = date_range[1].strftime("%Y-%m-%d")
        file_name = f"tiktok_summary_{export_granularity.lower()}_{start_str}_to_{end_str}.xlsx"

        st.download_button(
            label="📥 Download Aggregated Excel Report",
            data=output.getvalue(),
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No data to export for the selected filters.")

    # 📧 Send Weekly Email Data (GCS Upload & Zapier) - Admin Only
    if st.session_state.get("is_admin"):
        st.subheader("📧 Send Weekly Email Data")

        # Condition to show the button: filtered_data, summary_df, start_str, end_str, and output (Excel bytes) must be available
        if not filtered_data.empty and 'summary_df' in locals() and 'start_str' in locals() and 'end_str' in locals() and 'output' in locals() and 'file_name' in locals():
            if st.button("🚀 Send Data to Zapier for Weekly Email"):
                if "gcp" not in st.secrets or "gcs_bucket_name" not in st.secrets:
                    st.error("GCP credentials or GCS bucket name not found in secrets.")
                elif "zapier_webhook_url" not in st.secrets:
                    st.error("Zapier webhook URL not found in secrets.")
                else:
                    with st.spinner("Preparing charts and sending data to Zapier..."):
                        # Prepare data for the 5 specific charts
                        # Ensure 'orders_(sku)' is the correct column name from your data
                        required_metrics_for_charts = {
                            'cost': 'Cost',
                            'gross_revenue': 'Gross Revenue',
                            'orders_(sku)': 'Orders', # Assuming 'orders' in prompt means 'orders_(sku)'
                        }
                        
                        # Aggregate data for sum-based metrics
                        zapier_chart_data_agg = filtered_data.groupby(['report_date', 'campaign_name']).agg(
                            **{metric: (metric, 'sum') for metric in required_metrics_for_charts.keys()}
                        ).reset_index()

                        # Calculate ROI and CPO for these aggregated groups
                        zapier_chart_data_agg['roi'] = (zapier_chart_data_agg['gross_revenue'] / zapier_chart_data_agg['cost'])
                        zapier_chart_data_agg['cost_per_order'] = (zapier_chart_data_agg['cost'] / zapier_chart_data_agg['orders_(sku)'])
                        
                        # Handle potential NaN/inf values from division
                        zapier_chart_data_agg.replace([float('inf'), -float('inf')], pd.NA, inplace=True) # Use pd.NA for consistency
                        zapier_chart_data_agg['roi'] = zapier_chart_data_agg['roi'].fillna(0)
                        zapier_chart_data_agg['cost_per_order'] = zapier_chart_data_agg['cost_per_order'].fillna(0)

                        target_charts_to_upload = {
                            "cost": "Cost",
                            "gross_revenue": "Gross Revenue",
                            "roi": "ROI",
                            "orders_(sku)": "Orders", # Maps to 'orders_(sku)' column
                            "cost_per_order": "Cost Per Order"
                        }
                        
                        zapier_chart_urls = {}
                        all_charts_uploaded = True
                        excel_report_url = None

                        # 1. Upload Excel Report
                        st.write("Uploading Excel report to GCS...")
                        excel_bytes_to_upload = output.getvalue() # Get bytes from the existing 'output' BytesIO
                        excel_report_url = upload_excel_to_gcs(
                            excel_bytes_to_upload,
                            st.secrets["gcs_bucket_name"],
                            st.secrets["gcp"],
                            original_filename=file_name # Use the generated file_name
                        )

                        if not excel_report_url:
                            st.error("Failed to upload Excel report. Aborting Zapier send.")
                            all_charts_uploaded = False # Use this flag to prevent further processing
                        else:
                            st.write(f"Excel report uploaded: {excel_report_url}")

                        # 2. Upload Charts (only if Excel upload was successful)
                        if all_charts_uploaded: # Check if Excel upload was successful
                            for metric_col, display_name in target_charts_to_upload.items():
                                st.write(f"Generating chart for {display_name}...")
                                chart_obj = generate_specific_metric_chart(
                                    chart_df=zapier_chart_data_agg, # Use the aggregated and calculated data
                                    metric_col_name=metric_col,
                                    display_metric_name=display_name
                                )
                                if chart_obj:
                                    st.write(f"Uploading {display_name} chart to GCS...")
                                    image_url = upload_chart_to_gcs(
                                        chart_obj,
                                        st.secrets["gcs_bucket_name"],
                                        st.secrets["gcp"]
                                    )
                                    if image_url:
                                        zapier_chart_urls[f"{metric_col.replace('_(sku)', '')}_url"] = image_url # e.g., orders_url
                                        st.write(f"{display_name} chart uploaded: {image_url}")
                                    else:
                                        st.error(f"Failed to upload {display_name} chart.")
                                        all_charts_uploaded = False
                                        break # Stop if one chart fails
                                else:
                                    st.error(f"Failed to generate chart for {display_name}.")
                                    all_charts_uploaded = False
                                    break # Stop if one chart fails to generate


                        if all_charts_uploaded and excel_report_url and len(zapier_chart_urls) == len(target_charts_to_upload):
                            # Prepare payload for Zapier
                            payload = {
                                "start_date": start_str, # Defined in export section
                                "end_date": end_str,     # Defined in export section
                                "summary_data": summary_df.to_dict(orient="records"), # summary_df from export section
                                "excel_report_url": excel_report_url, # Add Excel report URL
                                "chart_images": zapier_chart_urls
                            }

                            # Send to Zapier
                            try:
                                response = requests.post(st.secrets["zapier_webhook_url"], json=payload)
                                response.raise_for_status() # Raise an exception for HTTP errors
                                st.success("✅ Data and chart images successfully sent to Zapier!")
                                st.balloons()
                            except requests.exceptions.RequestException as e:
                                st.error(f"❌ Failed to send data to Zapier: {e}")
                                if 'response' in locals() and response is not None:
                                    st.error(f"Zapier response: {response.text}")
                                else:
                                    st.error("No response object from Zapier.")
                        elif not excel_report_url:
                            # Error already shown by upload_excel_to_gcs or the check above
                            pass 
                        elif not all_charts_uploaded:
                            st.error("❌ Not all charts were uploaded successfully. Data not sent to Zapier.")
                        else:
                            st.error("❌ Chart generation or upload failed for some charts. Data not sent to Zapier.")
        elif 'summary_df' not in locals() or 'output' not in locals():
            st.info("Generate an export report first (which creates summary data and the Excel file) to enable sending data to Zapier.")
        else: # filtered_data is empty
            st.info("No data available for the current filters to send to Zapier.")

    # Historical data query
    if st.button('📊 View Historical Data'):
        records = sh.get_all_records()
        history_df = pd.DataFrame(records)
        st.write("Historical Ad Report Data:")
        st.dataframe(history_df)

# --- Authentication Flow ---
ENABLE_AUTH = os.getenv("STREAMLIT_ENABLE_AUTH", "false").lower() == "true"

if not ENABLE_AUTH:
    # Authentication is disabled, grant full access by default for local development
    if "authenticated" not in st.session_state: # Initialize if not already set by a previous run
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
        st.stop() # Stop execution if login form is shown and not successfully submitted
    
    # If we reach here, authentication is enabled AND user is authenticated.
    
    # Sidebar elements for authenticated users when auth is enabled
    with st.sidebar:
        if st.button("🔒 Logout"):
            if "authenticated" in st.session_state:
                del st.session_state.authenticated
            if "is_admin" in st.session_state:
                del st.session_state.is_admin
            st.rerun()

        # Allow non-admins to enter admin key later (only if auth is enabled)
        # Ensure is_admin exists before checking its value
        if "is_admin" not in st.session_state: # Should be set by login, but as a safeguard
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
                    elif admin_key_input: # if a key was entered but it's wrong
                        st.sidebar.error("Incorrect admin key.")
    
    # Ensure default state for admin if not explicitly set after login/admin key attempt
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    run_main_app()
