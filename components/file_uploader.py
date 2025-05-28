import streamlit as st
import pandas as pd
import re
import datetime
from utils.helpers import extract_account

def render_file_uploader(sheet):
    """Render file upload functionality for admin users."""
    st.markdown("## 🔼 Upload Daily Reports")
    uploaded_files = st.file_uploader(
        "📂 Upload one or more daily ad reports (.xlsx)",
        type="xlsx",
        accept_multiple_files=True,
        key="uploader"
    )

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

        if all_data:
            if st.button("✅ Upload All to Google Sheets"):
                upload_data_to_sheets(all_data, sheet)
                # Clear uploader input by resetting session state
                st.session_state["clear_uploader"] = True
                st.rerun()
    return all_data

def upload_data_to_sheets(all_data, sh):
    """Process and upload data to Google Sheets."""
    final_df = pd.DataFrame() # Initialize final_df as an empty DataFrame

    # Combine uploaded data into one DataFrame
    combined_df = pd.concat(all_data, ignore_index=True)

    # Add "account_name" column using the helper function (normalized name)
    if 'campaign_name' in combined_df.columns:
        combined_df['account_name'] = combined_df['campaign_name'].apply(extract_account)
    else:
        # If campaign_name is somehow missing in uploaded data, fill with default
        combined_df['account_name'] = "Other Accounts" 

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

    # Calculate total rows needed for the new data
    num_new_rows = len(rows_to_upload)
    
    # Get current max rows in the sheet
    current_max_rows = sh.row_count

    # Check if we need to add more rows to the sheet
    # next_row is 1-based, num_new_rows is the count of rows to add.
    # If next_row is 1 (empty sheet after headers), and we add 10 rows, we need 10 rows.
    # If next_row is 1114 (last current row), and we add 5 rows, we need 1113 (start) + 5 = 1118 rows.
    # The actual row number we will write up to is next_row + num_new_rows -1 (if next_row is where data starts)
    # However, if is_first_upload is true, rows_to_upload includes headers.
    
    # Simplified logic: what's the highest row number we'll touch?
    # If it's a first upload, rows_to_upload includes headers, so num_new_rows is correct.
    # If not, next_row is the first empty row, and we add num_new_rows data rows.
    # The highest row index will be next_row + num_new_rows - 1.
    
    required_rows_in_sheet = next_row + num_new_rows -1
    if not is_first_upload: # if not first upload, headers are not in rows_to_upload
        pass # next_row is already the first empty row, so required_rows_in_sheet is correct
    else: # if first_upload, next_row is 1, and rows_to_upload includes headers
        required_rows_in_sheet = num_new_rows # We need as many rows as we are uploading (data + header)


    if required_rows_in_sheet > current_max_rows:
        rows_to_add = required_rows_in_sheet - current_max_rows
        sh.add_rows(rows_to_add)
        st.info(f"Added {rows_to_add} row(s) to the sheet to accommodate new data.")

    # Upload to Google Sheet
    sh.update(f'A{next_row}', rows_to_upload)

    # Show success and rerun app to reflect updated data
    st.success(f'🎉 Uploaded {len(all_data)} file(s) successfully!')
    st.toast("Upload complete!", icon="✅")