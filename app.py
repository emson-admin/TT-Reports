import streamlit as st
import pandas as pd
import datetime
import gspread
import re
import io
from google.oauth2.service_account import Credentials
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill

if "authenticated" not in st.session_state:
    st.title("🔒 Protected Dashboard")
    pw = st.text_input("Enter access password", type="password")
    if pw == st.secrets["app_password"]:
        st.session_state.authenticated = True
        st.rerun()  # ✅ updated from experimental_rerun()
    elif pw:
        st.error("Incorrect password")
    st.stop()

st.set_page_config(layout="wide")

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
uploaded_files = st.file_uploader(
    "📂 Upload one or more daily ad reports (.xlsx)",
    type="xlsx",
    accept_multiple_files=True,
    key="uploader"  # so we can reset it
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
                    ).query('_merge == "left_only"').drop(columns=['_merge'])
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

    import altair as alt
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


# Historical data query
if st.button('📊 View Historical Data'):
    records = sh.get_all_records()
    history_df = pd.DataFrame(records)
    st.write("Historical Ad Report Data:")
    st.dataframe(history_df)
