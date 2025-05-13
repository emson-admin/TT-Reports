import streamlit as st
import pandas as pd
import requests
from services.cloud_storage import upload_excel_to_gcs, upload_chart_to_gcs
from utils.visualization import generate_specific_metric_chart

def send_weekly_email_data(filtered_data, export_data, secrets):
    """
    Prepare and send weekly email data to Zapier.
    
    Args:
        filtered_data: The filtered DataFrame of ad data
        export_data: Dictionary with export information (summary_df, output, file_name)
        secrets: Streamlit secrets dictionary
    """
    st.subheader("📧 Send Weekly Email Data")
    
    if not filtered_data.empty and export_data:
        summary_df = export_data["summary_df"]
        output = export_data["output"]
        file_name = export_data["file_name"]
        
        start_str = filtered_data['report_date'].min().strftime("%Y-%m-%d")
        end_str = filtered_data['report_date'].max().strftime("%Y-%m-%d")

        if st.button("🚀 Send Data to Zapier for Weekly Email"):
            if "gcp" not in secrets or "gcs_bucket_name" not in secrets:
                st.error("GCP credentials or GCS bucket name not found in secrets.")
            elif "zapier_webhook_url" not in secrets:
                st.error("Zapier webhook URL not found in secrets.")
            else:
                with st.spinner("Preparing charts and sending data to Zapier..."):
                    # Prepare data and upload to GCS
                    result = prepare_and_upload_data(filtered_data, output, file_name, start_str, end_str, summary_df, secrets)
                    
                    if result["success"]:
                        st.success("✅ Data and chart images successfully sent to Zapier!")
                        st.balloons()
                    else:
                        st.error(f"❌ {result['error']}")
    elif 'summary_df' not in (export_data or {}):
        st.info("Generate an export report first (which creates summary data and the Excel file) to enable sending data to Zapier.")
    else:
        st.info("No data available for the current filters to send to Zapier.")

def prepare_and_upload_data(filtered_data, excel_bytes, file_name, start_str, end_str, summary_df, secrets):
    """Prepare data for Zapier, including chart generation and uploads to GCS."""
    # Define required metrics for charts
    required_metrics_for_charts = {
        'cost': 'Cost',
        'gross_revenue': 'Gross Revenue',
        'orders_(sku)': 'Orders',
    }
    
    # Aggregate data for sum-based metrics
    zapier_chart_data_agg = filtered_data.groupby(['report_date', 'campaign_name']).agg(
        **{metric: (metric, 'sum') for metric in required_metrics_for_charts.keys()}
    ).reset_index()

    # Calculate ROI and CPO for these aggregated groups
    zapier_chart_data_agg['roi'] = (zapier_chart_data_agg['gross_revenue'] / zapier_chart_data_agg['cost'])
    zapier_chart_data_agg['cost_per_order'] = (zapier_chart_data_agg['cost'] / zapier_chart_data_agg['orders_(sku)'])
    
    # Handle potential NaN/inf values from division
    zapier_chart_data_agg.replace([float('inf'), -float('inf')], pd.NA, inplace=True)
    zapier_chart_data_agg['roi'] = zapier_chart_data_agg['roi'].fillna(0)
    zapier_chart_data_agg['cost_per_order'] = zapier_chart_data_agg['cost_per_order'].fillna(0)

    # Define charts to generate and upload
    target_charts_to_upload = {
        "cost": "Cost",
        "gross_revenue": "Gross Revenue",
        "roi": "ROI",
        "orders_(sku)": "Orders",
        "cost_per_order": "Cost Per Order"
    }
    
    # Upload Excel Report first
    st.write("Uploading Excel report to GCS...")
    excel_bytes_to_upload = excel_bytes.getvalue()
    excel_report_url = upload_excel_to_gcs(
        excel_bytes_to_upload,
        secrets["gcs_bucket_name"],
        secrets["gcp"],
        original_filename=file_name
    )

    if not excel_report_url:
        return {"success": False, "error": "Failed to upload Excel report. Aborting Zapier send."}
    
    st.write(f"Excel report uploaded: {excel_report_url}")
    
    # Upload Charts
    zapier_chart_urls = {}
    all_charts_uploaded = True
    
    for metric_col, display_name in target_charts_to_upload.items():
        st.write(f"Generating chart for {display_name}...")
        chart_obj = generate_specific_metric_chart(
            chart_df=zapier_chart_data_agg,
            metric_col_name=metric_col,
            display_metric_name=display_name
        )
        
        if chart_obj:
            st.write(f"Uploading {display_name} chart to GCS...")
            image_url = upload_chart_to_gcs(
                chart_obj,
                secrets["gcs_bucket_name"],
                secrets["gcp"]
            )
            
            if image_url:
                zapier_chart_urls[f"{metric_col.replace('_(sku)', '')}_url"] = image_url
                st.write(f"{display_name} chart uploaded: {image_url}")
            else:
                all_charts_uploaded = False
                return {"success": False, "error": f"Failed to upload {display_name} chart."}
        else:
            all_charts_uploaded = False
            return {"success": False, "error": f"Failed to generate chart for {display_name}."}

    # If all uploads succeeded, send to Zapier
    if all_charts_uploaded and excel_report_url and len(zapier_chart_urls) == len(target_charts_to_upload):
        # Prepare payload for Zapier
        payload = {
            "start_date": start_str,
            "end_date": end_str,
            "summary_data": summary_df.to_dict(orient="records"),
            "excel_report_url": excel_report_url,
            "chart_images": zapier_chart_urls
        }

        # Send to Zapier
        try:
            response = requests.post(secrets["zapier_webhook_url"], json=payload)
            response.raise_for_status()
            return {"success": True}
        except requests.exceptions.RequestException as e:
            error_message = f"Failed to send data to Zapier: {e}"
            if 'response' in locals() and response is not None:
                error_message += f"\nZapier response: {response.text}"
            return {"success": False, "error": error_message}
    else:
        return {"success": False, "error": "Chart generation or upload failed."}