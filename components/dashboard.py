import streamlit as st
import pandas as pd
import altair as alt
from utils.visualization import generate_multi_metric_line_chart, create_side_by_side_charts

def render_main_metrics_chart(filtered_data, main_metrics):
    """Render the main metrics chart."""
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

        line_chart = generate_multi_metric_line_chart(melted, main_metrics)
        st.altair_chart(line_chart, use_container_width=True)

def render_side_metric_charts(filtered_data, side_metrics):
    """Render side-by-side metric charts."""
    if not filtered_data.empty and side_metrics:
        st.subheader("📊 Side-by-Side Metric Charts by Campaign")

        charts = create_side_by_side_charts(filtered_data, side_metrics)
        
        for chart_row in charts:
            cols = st.columns(len(chart_row))
            for i, chart in enumerate(chart_row):
                with cols[i]:
                    st.altair_chart(chart, use_container_width=False)

def render_top_campaigns(filtered_data):
    """Render top 3 campaigns based on orders or revenue within the current filtered data."""
    if not filtered_data.empty:
        # Determine which metric to use for ranking (prefer orders, then revenue)
        rank_column = None
        if 'orders_(sku)' in filtered_data.columns:
            rank_column = 'orders_(sku)'
            metric_display = 'Orders'
        elif 'gross_revenue' in filtered_data.columns:
            rank_column = 'gross_revenue'
            metric_display = 'Revenue'
        else:
            return # If neither column exists, don't display anything
        
        # Group by campaign and aggregate multiple metrics
        metrics_to_aggregate = [rank_column]
        if 'gross_revenue' in filtered_data.columns and rank_column != 'gross_revenue':
            metrics_to_aggregate.append('gross_revenue')
        if 'cost' in filtered_data.columns:
            metrics_to_aggregate.append('cost')
            
        # Get summary for ALL campaigns (we'll use this later for the remaining campaigns table)
        all_campaign_summary = (filtered_data
                          .groupby('campaign_name')[metrics_to_aggregate]
                          .sum()
                          .reset_index()
                          .sort_values(rank_column, ascending=False))
        
        # Calculate ROI if we have revenue and cost data
        if 'gross_revenue' in all_campaign_summary.columns and 'cost' in all_campaign_summary.columns:
            all_campaign_summary['roi'] = all_campaign_summary['gross_revenue'] / all_campaign_summary['cost']
            # Replace infinite values (division by zero) with 0
            all_campaign_summary['roi'] = all_campaign_summary['roi'].replace([float('inf'), -float('inf')], 0)
            all_campaign_summary['roi'] = all_campaign_summary['roi'].fillna(0)
        
        # Get top 3 for the featured display AFTER calculating ROI
        campaign_summary = all_campaign_summary.head(3)
        
        if not campaign_summary.empty:
            st.markdown("### 🏆 Top Campaigns")
            
            # Create columns for the top campaigns
            cols = st.columns(3)
            
            # Add CSS for the boxes
            st.markdown("""
            <style>
            .top-campaign-box {
                background-color: #f0f2f6;
                border-radius: 10px;
                padding: 10px 15px;
                height: 100%;
            }
            .campaign-name {
                text-align: center;
                margin-bottom: 8px;
            }
            .campaign-metrics {
                font-size: 0.9rem;
                margin: 4px 0;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Fill in the columns with campaign data
            for i, ((_, row), col) in enumerate(zip(campaign_summary.iterrows(), cols)):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
                
                # Prepare metrics with consistent formatting
                metrics_html = f"<p class='campaign-metrics'>{metric_display}: <strong>{int(row[rank_column]):,}</strong></p>"
                
                # Add spend (cost)
                if 'cost' in row:
                    metrics_html += f"<p class='campaign-metrics'>Spend: <strong>${row['cost']:,.2f}</strong></p>"
                
                if 'gross_revenue' in row:
                    metrics_html += f"<p class='campaign-metrics'>Revenue: <strong>${row['gross_revenue']:,.2f}</strong></p>"
                    
                if 'roi' in row:
                    metrics_html += f"<p class='campaign-metrics'>ROI: <strong>{row['roi']:.2f}x</strong></p>"
                
                col.markdown(f"""
                <div class="top-campaign-box">
                    <h4 class="campaign-name">{medal} {row['campaign_name']}</h4>
                    {metrics_html}
                </div>
                """, unsafe_allow_html=True)
            
            # If there are fewer than 3 campaigns, fill the remaining columns with empty boxes
            for i in range(len(campaign_summary), 3):
                cols[i].markdown(f"""
                <div class="top-campaign-box" style="opacity: 0.5;">
                    <h4 class="campaign-name">No data</h4>
                    <p>&nbsp;</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Display the remaining campaigns in a table format
            if len(all_campaign_summary) > 3:
                st.markdown("### 📊 Remaining Campaigns")
                
                # Get the remaining campaigns (after the top 3)
                remaining_campaigns = all_campaign_summary.iloc[3:].copy()
                
                # Format the columns for display
                display_df = remaining_campaigns.copy()
                
                # Format the numeric columns
                if 'cost' in display_df.columns:
                    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:,.2f}")
                
                if 'gross_revenue' in display_df.columns:
                    display_df['gross_revenue'] = display_df['gross_revenue'].apply(lambda x: f"${x:,.2f}")
                
                if 'roi' in display_df.columns:
                    display_df['roi'] = display_df['roi'].apply(lambda x: f"{x:.2f}x")
                
                if rank_column == 'orders_(sku)' and 'orders_(sku)' in display_df.columns:
                    display_df['orders_(sku)'] = display_df['orders_(sku)'].apply(lambda x: f"{int(x):,}")
                
                # Rename columns for better display
                column_rename = {
                    'campaign_name': 'Campaign',
                    'cost': 'Spend',
                    'gross_revenue': 'Revenue',
                    'roi': 'ROI',
                    'orders_(sku)': 'Orders'
                }
                display_df = display_df.rename(columns=column_rename)
                
                # Reorder columns for consistent display
                ordered_columns = ['Campaign']
                if 'Orders' in display_df.columns:
                    ordered_columns.append('Orders')
                if 'Spend' in display_df.columns:
                    ordered_columns.append('Spend')
                if 'Revenue' in display_df.columns:
                    ordered_columns.append('Revenue')
                if 'ROI' in display_df.columns:
                    ordered_columns.append('ROI')
                
                # Filter to only include columns that exist
                ordered_columns = [col for col in ordered_columns if col in display_df.columns]
                display_df = display_df[ordered_columns]
                
                # Display the table
                st.dataframe(display_df, use_container_width=True)

def render_kpi_summary(filtered_data):
    """Render KPI summary metrics."""
    st.subheader("📌 Summary Metrics")

    if not filtered_data.empty:
        # Ensure all required metric columns exist before trying to sum or mean them
        kpi_metrics = ['cost', 'gross_revenue', 'orders_(sku)', 'roi', 'cost_per_order']
        existing_kpi_metrics = [m for m in kpi_metrics if m in filtered_data.columns]

        total_cost = filtered_data['cost'].sum() if 'cost' in existing_kpi_metrics else 0
        total_revenue = filtered_data['gross_revenue'].sum() if 'gross_revenue' in existing_kpi_metrics else 0
        total_orders = filtered_data['orders_(sku)'].sum() if 'orders_(sku)' in existing_kpi_metrics else 0
        avg_roi = (total_revenue / total_cost) if total_cost > 0 else 0  # Calculate ROI based on total cost and revenue
        avg_cpo = filtered_data['cost_per_order'].mean() if 'cost_per_order' in existing_kpi_metrics else 0
        
        # Handle potential NaN from .mean() if all values were NaN (e.g. for a single row with NaN)
        avg_cpo = 0 if pd.isna(avg_cpo) else avg_cpo

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Cost", f"${total_cost:,.2f}")
        col2.metric("📈 Gross Revenue", f"${total_revenue:,.2f}")
        col3.metric("📊 Avg ROI/MER", f"{avg_roi:.2f}x")

        col4, col5 = st.columns(2)
        col4.metric("📦 Total Orders", f"{int(total_orders):,}")
        col5.metric("🧾 Avg Cost/Order", f"${avg_cpo:,.2f}")
        
        # Add the top campaigns section
        render_top_campaigns(filtered_data)
    else:
        st.info("No data to summarize for the current filter selection.")

def render_historical_data_view(sheet):
    """Render the historical data view."""
    if st.button('📊 View Historical Data'):
        records = sheet.get_all_records()
        history_df = pd.DataFrame(records)
        st.write("Historical Ad Report Data:")
        st.dataframe(history_df)

def filter_data(data, filter_options):
    """Filter data based on selected filter options."""
    if data.empty:
        return pd.DataFrame()  # Return empty DataFrame if input is empty

    date_range = filter_options["date_range"]
    selected_accounts = filter_options["selected_accounts"]
    selected_campaigns = filter_options["selected_campaigns"]

    # Date filter
    base_mask = (
        (data['report_date'] >= pd.to_datetime(date_range[0])) &
        (data['report_date'] <= pd.to_datetime(date_range[1]))
    )

    # Campaign filter
    if 'campaign_name' in data.columns:
        base_mask &= data['campaign_name'].isin(selected_campaigns)

    # Account filter
    if 'account_name' in data.columns:
        if selected_accounts:  # If something is selected
            if "All Accounts" not in selected_accounts:
                base_mask &= data['account_name'].isin(selected_accounts)
        else:  # If nothing is selected
            base_mask &= data['account_name'].isin([])  # Returns False

    return data[base_mask]

def render_dashboard(data, filter_options, sheet):
    """Render the entire dashboard."""
    # Filter data based on user selections
    filtered_data = filter_data(data, filter_options)
    
    # Show message if no data to display
    if filtered_data.empty:
        st.info("No data to display with the current filter selections.")
        return filtered_data
    
    # Main chart
    render_main_metrics_chart(filtered_data, filter_options["main_metrics"])
    
    # Side-by-side charts
    render_side_metric_charts(filtered_data, filter_options["side_metrics"])
    
    # KPI summary
    render_kpi_summary(filtered_data)
    
    return filtered_data