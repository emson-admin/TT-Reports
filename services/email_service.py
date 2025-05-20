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
    target_charts_to_upload = {
        "gross_revenue": "Gross Revenue",
        "cost": "Cost",
        "roi": "ROI",
        "orders_(sku)": "Orders",
        "cost_per_order": "Cost Per Order"
    }
    
    # Aggregate data for sum-based metrics
    zapier_chart_data_agg = filtered_data.groupby(['report_date', 'campaign_name'])[list(target_charts_to_upload.keys())].sum().reset_index()
    
    # Calculate ROI and CPO (these are calculated metrics)
    zapier_chart_data_agg['roi'] = (zapier_chart_data_agg['gross_revenue'] / zapier_chart_data_agg['cost'])
    zapier_chart_data_agg['cost_per_order'] = (zapier_chart_data_agg['cost'] / zapier_chart_data_agg['orders_(sku)'])
    
    # Handle potential NaN/inf values from division
    zapier_chart_data_agg.replace([float('inf'), -float('inf')], pd.NA, inplace=True)
    zapier_chart_data_agg['roi'] = zapier_chart_data_agg['roi'].fillna(0)
    zapier_chart_data_agg['cost_per_order'] = zapier_chart_data_agg['cost_per_order'].fillna(0)
    
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
    
    # Calculate summary metrics for Zapier
    summary_metrics = get_summary_metrics(filtered_data)
    
    # Get top campaigns and remaining campaigns data
    top_campaigns_data, remaining_campaigns_data = get_campaign_data(filtered_data)

    # If all uploads succeeded, send to Zapier
    if all_charts_uploaded and excel_report_url:
        # Prepare payload for Zapier
        payload = {
            "start_date": start_str,
            "end_date": end_str,
            "excel_report_url": excel_report_url,
            "chart_images": zapier_chart_urls,
            "summary_metrics": summary_metrics,
            "top_campaigns": top_campaigns_data,
            "remaining_campaigns": remaining_campaigns_data
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

def get_summary_metrics(filtered_data):
    """Calculate summary metrics for Zapier."""
    # Ensure all required metric columns exist
    kpi_metrics = ['cost', 'gross_revenue', 'orders_(sku)', 'roi', 'cost_per_order']
    existing_kpi_metrics = [m for m in kpi_metrics if m in filtered_data.columns]

    total_cost = filtered_data['cost'].sum() if 'cost' in existing_kpi_metrics else 0
    total_revenue = filtered_data['gross_revenue'].sum() if 'gross_revenue' in existing_kpi_metrics else 0
    total_orders = filtered_data['orders_(sku)'].sum() if 'orders_(sku)' in existing_kpi_metrics else 0
    avg_roi = (total_revenue / total_cost) if total_cost > 0 else 0
    avg_cpo = filtered_data['cost_per_order'].mean() if 'cost_per_order' in existing_kpi_metrics else 0
    avg_cpo = 0 if pd.isna(avg_cpo) else avg_cpo

    return {
        "total_cost": f"${total_cost:,.2f}",
        "total_revenue": f"${total_revenue:,.2f}",
        "total_orders": f"{int(total_orders):,}",
        "avg_roi": f"{avg_roi:.2f}x",
        "avg_cost_per_order": f"${avg_cpo:,.2f}",
        "raw_values": {
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "total_orders": int(total_orders),
            "avg_roi": avg_roi,
            "avg_cost_per_order": avg_cpo
        }
    }

def get_campaign_data(filtered_data):
    """Get top 3 campaigns and remaining campaigns data for Zapier."""
    if filtered_data.empty:
        return [], []
        
    # Determine which metric to use for ranking
    rank_column = 'orders_(sku)' if 'orders_(sku)' in filtered_data.columns else 'gross_revenue'
    
    # Set up metrics to aggregate
    metrics_to_aggregate = [rank_column]
    if 'gross_revenue' in filtered_data.columns and rank_column != 'gross_revenue':
        metrics_to_aggregate.append('gross_revenue')
    if 'cost' in filtered_data.columns:
        metrics_to_aggregate.append('cost')
    
    # Aggregate data
    campaign_summary = (filtered_data
                      .groupby('campaign_name')[metrics_to_aggregate]
                      .sum()
                      .reset_index()
                      .sort_values(rank_column, ascending=False))
    
    # Calculate ROI
    if 'gross_revenue' in campaign_summary.columns and 'cost' in campaign_summary.columns:
        campaign_summary['roi'] = campaign_summary['gross_revenue'] / campaign_summary['cost']
        campaign_summary['roi'] = campaign_summary['roi'].replace([float('inf'), -float('inf')], 0).fillna(0)
    
    # Format data for top 3 campaigns
    top_campaigns_data = []
    if not campaign_summary.empty:
        for _, row in campaign_summary.head(3).iterrows():
            campaign_data = {
                "name": row['campaign_name'],
                "metrics": {}
            }
            
            # Add orders/revenue (ranking metric)
            if rank_column == 'orders_(sku)':
                campaign_data["metrics"]["orders"] = int(row[rank_column])
                campaign_data["metrics"]["orders_formatted"] = f"{int(row[rank_column]):,}"
            
            # Add cost
            if 'cost' in row:
                campaign_data["metrics"]["cost"] = float(row['cost'])
                campaign_data["metrics"]["cost_formatted"] = f"${row['cost']:,.2f}"
            
            # Add revenue
            if 'gross_revenue' in row:
                campaign_data["metrics"]["revenue"] = float(row['gross_revenue'])
                campaign_data["metrics"]["revenue_formatted"] = f"${row['gross_revenue']:,.2f}"
            
            # Add ROI
            if 'roi' in row:
                campaign_data["metrics"]["roi"] = float(row['roi'])
                campaign_data["metrics"]["roi_formatted"] = f"{row['roi']:.2f}x"
            
            top_campaigns_data.append(campaign_data)
    
    # Format data for remaining campaigns (after top 3)
    remaining_campaigns_data = []
    if len(campaign_summary) > 3:
        for _, row in campaign_summary.iloc[3:].iterrows():
            campaign_data = {
                "name": row['campaign_name'],
                "metrics": {}
            }
            
            # Add orders/revenue (ranking metric)
            if rank_column == 'orders_(sku)':
                campaign_data["metrics"]["orders"] = int(row[rank_column])
                campaign_data["metrics"]["orders_formatted"] = f"{int(row[rank_column]):,}"
            
            # Add cost
            if 'cost' in row:
                campaign_data["metrics"]["cost"] = float(row['cost'])
                campaign_data["metrics"]["cost_formatted"] = f"${row['cost']:,.2f}"
            
            # Add revenue
            if 'gross_revenue' in row:
                campaign_data["metrics"]["revenue"] = float(row['gross_revenue'])
                campaign_data["metrics"]["revenue_formatted"] = f"${row['gross_revenue']:,.2f}"
            
            # Add ROI
            if 'roi' in row:
                campaign_data["metrics"]["roi"] = float(row['roi'])
                campaign_data["metrics"]["roi_formatted"] = f"{row['roi']:.2f}x"
            
            remaining_campaigns_data.append(campaign_data)
    
    return top_campaigns_data, remaining_campaigns_data