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

def render_top_campaigns(filtered_data, date_range=None, full_data=None):
    """Render top 3 campaigns based on orders or revenue within the current filtered data.
    
    Args:
        filtered_data: Current period data
        date_range: Current date range tuple (start_date, end_date)
        full_data: Complete dataset for calculating previous period
    """
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
            
            # Display all campaigns in a table format
            if len(all_campaign_summary) > 0:
                st.markdown("### 📊 All Campaigns")
                
                # Add toggle for comparing with previous period
                show_comparison = st.checkbox(
                    "📊 Compare with Previous Period",
                    key="show_period_comparison",
                    help="Shows change from previous period in parentheses (green for positive, red for negative)"
                )
                
                # Calculate previous period data if comparison is enabled
                if show_comparison and date_range and full_data is not None:
                    from datetime import timedelta
                    start_date, end_date = date_range
                    period_length = (end_date - start_date).days + 1
                    
                    # Calculate previous period dates
                    prev_end_date = start_date - timedelta(days=1)
                    prev_start_date = prev_end_date - timedelta(days=period_length - 1)
                    
                    # Filter data for previous period
                    prev_data = full_data[
                        (full_data['report_date'] >= pd.Timestamp(prev_start_date)) &
                        (full_data['report_date'] <= pd.Timestamp(prev_end_date))
                    ]
                    
                    if not prev_data.empty:
                        # Aggregate previous period data
                        prev_metrics = [col for col in metrics_to_aggregate if col in prev_data.columns]
                        prev_campaign_summary = (prev_data
                                                .groupby('campaign_name')[prev_metrics]
                                                .sum()
                                                .reset_index())
                        
                        # Calculate ROI for previous period
                        if 'gross_revenue' in prev_campaign_summary.columns and 'cost' in prev_campaign_summary.columns:
                            prev_campaign_summary['roi'] = prev_campaign_summary['gross_revenue'] / prev_campaign_summary['cost']
                            prev_campaign_summary['roi'] = prev_campaign_summary['roi'].replace([float('inf'), -float('inf')], 0)
                            prev_campaign_summary['roi'] = prev_campaign_summary['roi'].fillna(0)
                        
                        # Merge with current data
                        all_campaign_summary = all_campaign_summary.merge(
                            prev_campaign_summary,
                            on='campaign_name',
                            how='left',
                            suffixes=('', '_prev')
                        )
                        
                        # Calculate differences
                        for col in metrics_to_aggregate + ['roi']:
                            if col in all_campaign_summary.columns and f'{col}_prev' in all_campaign_summary.columns:
                                all_campaign_summary[f'{col}_diff'] = all_campaign_summary[col] - all_campaign_summary[f'{col}_prev'].fillna(0)
                                all_campaign_summary[f'{col}_pct'] = (
                                    (all_campaign_summary[f'{col}_diff'] / all_campaign_summary[f'{col}_prev'].replace(0, 1)) * 100
                                ).fillna(0)
                
                # Get all campaigns (including top 3)
                # Add an original rank based on their order in all_campaign_summary
                remaining_campaigns_df = all_campaign_summary.copy().reset_index(drop=True)
                remaining_campaigns_df.insert(0, '_OriginalRank', remaining_campaigns_df.index + 1)

                # --- Sorting Controls ---
                sort_options_map = {'Original Performance': '_OriginalRank'}
                if 'campaign_name' in remaining_campaigns_df.columns:
                    sort_options_map['Campaign Name'] = 'campaign_name'
                if 'orders_(sku)' in remaining_campaigns_df.columns:
                    sort_options_map['Orders'] = 'orders_(sku)'
                if 'cost' in remaining_campaigns_df.columns:
                    sort_options_map['Spend'] = 'cost'
                if 'gross_revenue' in remaining_campaigns_df.columns:
                    sort_options_map['Revenue'] = 'gross_revenue'
                if 'roi' in remaining_campaigns_df.columns:
                    sort_options_map['ROI'] = 'roi'
                
                col_sort_by, col_sort_order = st.columns(2)
                with col_sort_by:
                    sort_by_display = st.selectbox(
                        "Sort remaining by:",
                        options=list(sort_options_map.keys()),
                        key='remaining_sort_by',
                        index=0 # Default to 'Original Performance'
                    )
                with col_sort_order:
                    sort_order_display = st.radio(
                        "Order:",
                        options=["Ascending", "Descending"],
                        key='remaining_sort_order',
                        index=0, # Default to Ascending for Original Performance (4, 5, 6...)
                        horizontal=True
                    )
                
                actual_sort_column = sort_options_map[sort_by_display]
                is_ascending = sort_order_display == "Ascending"
                
                sorted_df = remaining_campaigns_df.sort_values(by=actual_sort_column, ascending=is_ascending)
                
                # Prepare dataframe for display (after sorting)
                display_df = sorted_df.reset_index(drop=True)
                
                # Format the numeric columns for display with comparison if enabled
                def format_with_comparison(value, prev_value=None, is_currency=False, is_roi=False, is_integer=False, is_cost=False):
                    """Format value with optional previous period value for comparison."""
                    if pd.isnull(value):
                        return "N/A"
                    
                    # Format the main value
                    if is_currency:
                        formatted = f"${value:,.2f}"
                    elif is_roi:
                        formatted = f"{value:.2f}x"
                    elif is_integer:
                        formatted = f"{int(value):,}"
                    else:
                        formatted = f"{value:,.2f}"
                    
                    # Add previous period value if available
                    if show_comparison and prev_value is not None and not pd.isnull(prev_value):
                        # Determine color based on whether current is better than previous
                        # For cost, lower is better; for everything else, higher is better
                        if is_cost:
                            color = "green" if value <= prev_value else "red"
                        else:
                            color = "green" if value >= prev_value else "red"
                        
                        # Format the previous value
                        if is_currency:
                            prev_formatted = f"${prev_value:,.0f}"
                        elif is_roi:
                            prev_formatted = f"{prev_value:.1f}x"
                        elif is_integer:
                            prev_formatted = f"{int(prev_value):,}"
                        else:
                            prev_formatted = f"{prev_value:,.0f}"
                        
                        formatted = f"{formatted} <span style='color: {color}; font-size: 0.9em;'>({prev_formatted})</span>"
                    
                    return formatted
                
                if 'cost' in display_df.columns:
                    prev_col = 'cost_prev' if show_comparison and 'cost_prev' in display_df.columns else None
                    display_df['cost'] = display_df.apply(
                        lambda row: format_with_comparison(
                            row['cost'], 
                            row[prev_col] if prev_col else None, 
                            is_currency=True,
                            is_cost=True
                        ), axis=1
                    )
                
                if 'gross_revenue' in display_df.columns:
                    prev_col = 'gross_revenue_prev' if show_comparison and 'gross_revenue_prev' in display_df.columns else None
                    display_df['gross_revenue'] = display_df.apply(
                        lambda row: format_with_comparison(
                            row['gross_revenue'], 
                            row[prev_col] if prev_col else None, 
                            is_currency=True
                        ), axis=1
                    )
                
                if 'roi' in display_df.columns:
                    prev_col = 'roi_prev' if show_comparison and 'roi_prev' in display_df.columns else None
                    display_df['roi'] = display_df.apply(
                        lambda row: format_with_comparison(
                            row['roi'], 
                            row[prev_col] if prev_col else None, 
                            is_roi=True
                        ), axis=1
                    )
                
                if 'orders_(sku)' in display_df.columns:
                    prev_col = 'orders_(sku)_prev' if show_comparison and 'orders_(sku)_prev' in display_df.columns else None
                    display_df['orders_(sku)'] = display_df.apply(
                        lambda row: format_with_comparison(
                            row['orders_(sku)'], 
                            row[prev_col] if prev_col else None, 
                            is_integer=True
                        ), axis=1
                    )
                
                # Rename columns for better display
                column_rename = {
                    'campaign_name': 'Campaign',
                    'cost': 'Spend',
                    'gross_revenue': 'Revenue',
                    'roi': 'ROI',
                    'orders_(sku)': 'Orders',
                    # '_OriginalRank': 'Initial Rank' # Optionally display this
                }
                display_df = display_df.rename(columns=column_rename)
                
                # Reorder columns for consistent display
                ordered_columns = ['Campaign']
                if 'Orders' in display_df.columns: ordered_columns.append('Orders')
                if 'Spend' in display_df.columns: ordered_columns.append('Spend')
                if 'Revenue' in display_df.columns: ordered_columns.append('Revenue')
                if 'ROI' in display_df.columns: ordered_columns.append('ROI')
                # if 'Initial Rank' in display_df.columns: ordered_columns.append('Initial Rank')

                # Filter to only include columns that exist and are in ordered_columns
                final_display_columns = [col for col in ordered_columns if col in display_df.columns]
                display_df_final = display_df[final_display_columns]
                
                # Display the table (use st.write to support HTML if comparison is enabled)
                if show_comparison:
                    # Convert to HTML to support colored text
                    html_table = display_df_final.to_html(escape=False, index=False)
                    st.write(html_table, unsafe_allow_html=True)
                else:
                    st.dataframe(display_df_final, use_container_width=True)
            else:
                st.info("No campaigns to display.")

def render_kpi_summary(filtered_data, date_range=None, full_data=None):
    """Render KPI summary metrics.
    
    Args:
        filtered_data: Current period data
        date_range: Current date range tuple (start_date, end_date)
        full_data: Complete dataset for calculating previous period
    """
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
        
        # Add the top campaigns section with date_range and full_data for comparison
        render_top_campaigns(filtered_data, date_range, full_data)
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
    
    # KPI summary with date range and full data for comparison
    date_range = filter_options.get("date_range")
    render_kpi_summary(filtered_data, date_range, data)
    
    return filtered_data