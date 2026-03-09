import streamlit as st
import pandas as pd
import re
import datetime
from utils.helpers import extract_account

def render_file_uploader(sheet):
    """Render file upload functionality for admin users."""
    st.markdown("## 🔼 Upload Daily Reports")
    
    # Add deduplication section for admins
    with st.expander("🧹 Data Maintenance"):
        st.markdown("### Remove Duplicate Rows")
        st.write("This will scan the Google Sheet for exact duplicate rows and remove them, keeping only the first occurrence of each duplicate.")
        
        if st.button("🔍 Check and Remove Duplicates"):
            from components.data_loader import deduplicate_sheet_data
            duplicates_removed = deduplicate_sheet_data(sheet)
            if duplicates_removed > 0:
                # Clear the cache to force reload of updated data
                st.cache_data.clear()
                st.rerun()
    
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

                # Clean & normalize column names
                df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(" ", "_").str.replace("(", "").str.replace(")", "")
                
                # Expected TikTok columns (core columns that should always be present)
                expected_columns = {'campaign_id', 'campaign_name', 'cost', 'net_cost', 'orders_sku', 'cost_per_order', 'gross_revenue', 'roi', 'currency'}

                # Optional columns that TikTok sometimes includes
                optional_columns = {'current_budget', 'daily_budget'}
                actual_columns = set(df.columns)
                
                # Check if format changed (only show warnings for missing core columns)
                missing_cols = expected_columns - actual_columns
                if missing_cols:
                    st.warning(f"⚠️ Missing expected columns in {file.name}: {missing_cols}")
                
                # Track new columns but show summary later (excluding known optional columns)
                extra_cols = actual_columns - expected_columns - optional_columns
                if extra_cols and 'new_columns_found' not in st.session_state:
                    st.session_state.new_columns_found = extra_cols
                
                # Handle new TikTok format - map column names
                column_mapping = {
                    'campaign_id': 'campaign_id',
                    'campaign_name': 'campaign_name', 
                    'cost': 'cost',
                    'net_cost': 'net_cost',
                    'orders_sku': 'orders_(sku)',
                    'cost_per_order': 'cost_per_order',
                    'gross_revenue': 'gross_revenue',
                    'roi': 'roi',
                    'currency': 'currency',
                    'daily_budget': 'daily_budget',
                    'current_budget': 'current_budget'
                }
                
                # Rename columns to match expected format
                df = df.rename(columns=column_mapping)
                
                # Parse date from filename (required since TikTok removed date column)
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

                # Convert campaign_id to string (without quote prefix)
                if 'campaign_id' in df.columns:
                    df['campaign_id'] = df['campaign_id'].astype(str)

                df['upload_date'] = datetime.datetime.now().strftime('%Y-%m-%d')

                all_data.append(df)

            except Exception as e:
                st.error(f"❌ Error processing {file.name}: {e}")

        if all_data:
            # Show summary of new columns found
            if 'new_columns_found' in st.session_state:
                st.info(f"ℹ️ New TikTok columns detected: {st.session_state.new_columns_found}")
                
            if st.button("✅ Upload All to Google Sheets"):
                upload_data_to_sheets(all_data, sheet)
                # Clear session state
                if 'new_columns_found' in st.session_state:
                    del st.session_state.new_columns_found
                st.session_state["clear_uploader"] = True
                st.rerun()
    return all_data

def upload_data_to_sheets(all_data, sh):
    """Process and upload data to Google Sheets."""
    final_df = pd.DataFrame() # Initialize final_df as an empty DataFrame

    # Combine uploaded data into one DataFrame
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Ensure combined_df has unique column names
    seen = {}
    unique_cols = []
    for col in combined_df.columns:
        col_str = str(col)
        if col_str in seen:
            seen[col_str] += 1
            unique_cols.append(f"{col_str}_{seen[col_str]}")
        else:
            seen[col_str] = 0
            unique_cols.append(col_str)
    combined_df.columns = unique_cols
    
    # Remove duplicates within the uploaded batch itself
    original_upload_count = len(combined_df)
    combined_df = combined_df.drop_duplicates(keep='first')
    internal_duplicates_removed = original_upload_count - len(combined_df)
    
    if internal_duplicates_removed > 0:
        st.info(f"ℹ️ Removed {internal_duplicates_removed} duplicate row(s) within the uploaded files.")

    # Add "account_name" column using the helper function (normalized name)
    if 'campaign_name' in combined_df.columns:
        combined_df['account_name'] = combined_df['campaign_name'].apply(extract_account)
    else:
        # If campaign_name is somehow missing in uploaded data, fill with default
        combined_df['account_name'] = "Other Accounts" 

    # Load existing data from sheet - use get_all_values() to handle duplicate headers
    all_values = sh.get_all_values()
    if all_values and len(all_values) > 1:
        # Create DataFrame with potentially duplicate column names
        headers = all_values[0]
        
        # Make column names unique by appending a counter to duplicates
        seen = {}
        unique_headers = []
        for header in headers:
            header_str = str(header).strip().lower().replace(" ", "_")
            if header_str in seen:
                seen[header_str] += 1
                unique_headers.append(f"{header_str}_{seen[header_str]}")
            else:
                seen[header_str] = 0
                unique_headers.append(header_str)
        
        existing = pd.DataFrame(all_values[1:], columns=unique_headers)
    else:
        existing = pd.DataFrame()

    # Ensure combined_df['report_date'] exists and is datetime
    combined_df['report_date'] = pd.to_datetime(combined_df['report_date'])
    if not existing.empty and 'report_date' in existing.columns:
        existing['report_date'] = pd.to_datetime(existing['report_date'])
        
        # Check for exact duplicate rows (all columns match)
        if not existing.empty:
            # Find common columns between upload and existing data
            common_columns = list(set(combined_df.columns) & set(existing.columns))
            
            if common_columns:
                # Convert datetime columns to string for comparison
                combined_df_comparison = combined_df.copy()
                existing_comparison = existing.copy()
                
                for col in common_columns:
                    if combined_df_comparison[col].dtype == 'datetime64[ns]':
                        combined_df_comparison[col] = combined_df_comparison[col].dt.strftime('%Y-%m-%d')
                    if existing_comparison[col].dtype == 'datetime64[ns]':
                        existing_comparison[col] = existing_comparison[col].dt.strftime('%Y-%m-%d')
                
                # Create a temporary merge key for exact duplicate detection
                combined_df_comparison['_temp_merge_key'] = combined_df_comparison[common_columns].astype(str).apply(lambda x: '|'.join(x), axis=1)
                existing_comparison['_temp_merge_key'] = existing_comparison[common_columns].astype(str).apply(lambda x: '|'.join(x), axis=1)
                
                # Find exact duplicates
                exact_duplicates = combined_df_comparison[combined_df_comparison['_temp_merge_key'].isin(existing_comparison['_temp_merge_key'])]
                
                if not exact_duplicates.empty:
                    st.warning(f"⚠️ Found {len(exact_duplicates)} exact duplicate row(s) that already exist in the sheet.")
                    
                    # Remove exact duplicates from upload
                    combined_df = combined_df[~combined_df_comparison['_temp_merge_key'].isin(existing_comparison['_temp_merge_key'])]
                    st.info(f"✅ Filtered out {len(exact_duplicates)} exact duplicate row(s) from upload.")
                    
                    # If no new data remains after filtering duplicates, stop here
                    if combined_df.empty:
                        st.info("ℹ️ No new data to upload after filtering duplicates.")
                        return

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
                st.warning(f"🚨 Found {len(duplicate_rows)} duplicate campaign+date combinations!")
                with st.expander(f"⚠️ View {len(duplicate_rows)} Duplicate Rows"):
                    st.dataframe(duplicate_rows[['campaign_id', 'campaign_name', 'report_date', 'cost']])

                # Ask user whether to overwrite or skip duplicate rows
                overwrite = st.radio(
                    f"⚠️ {len(duplicate_rows)} duplicate rows detected based on 'campaign_id' and 'report_date'. What would you like to do?",
                    ("Skip duplicates", "Overwrite duplicates"),
                    help="Skip: Keep existing data, ignore new duplicates. Overwrite: Replace existing with new data."
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
                    
                    # Combine with existing data
                    final_df = pd.concat([existing, final_df], ignore_index=True)
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
    
    # Check if sheet is completely empty or has no valid headers
    needs_headers = is_first_upload or (len(existing_records) > 0 and not any(existing_records[0]))
    
    if needs_headers:
        st.info("📝 Creating headers for empty sheet...")
        # Clear sheet first
        sh.clear()
        
    # Always ensure consistent column ordering for the final dataset
    standard_column_order = [
        'campaign_id', 'campaign_name', 'cost', 'net_cost', 'orders_(sku)', 
        'cost_per_order', 'gross_revenue', 'roi', 'currency', 'report_date', 
        'upload_date', 'account_name', 'daily_budget', 'current_budget'
    ]
    
    # Reorder final_df columns to match standard order, keeping only existing columns
    if not final_df.empty:
        existing_cols = [col for col in standard_column_order if col in final_df.columns]
        extra_cols = [col for col in final_df.columns if col not in standard_column_order]
        final_column_order = existing_cols + extra_cols
        final_df = final_df[final_column_order]
        
        # Update existing_records after clearing if needed
        if needs_headers:
            sh.update('A1', [final_df.columns.tolist()])
            existing_records = [final_df.columns.tolist()]
            is_first_upload = False

    # Convert any datetime columns to string format for JSON compatibility with gspread
    for col in final_df.select_dtypes(include=['datetime', 'datetime64[ns]']):
        final_df[col] = final_df[col].dt.strftime('%Y-%m-%d')
    
    # Ensure upload_date is properly formatted as string (not NaN)
    if 'upload_date' in final_df.columns:
        # Fill any NaN values with current date
        final_df['upload_date'] = final_df['upload_date'].fillna(datetime.datetime.now().strftime('%Y-%m-%d'))

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