import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

def render_trending_campaigns(data):
    """Render trending campaigns analysis with WoW and MoM comparisons."""
    
    st.markdown("## 📈 Trending Campaigns & Products")
    
    if data.empty:
        st.warning("No data available for trending analysis")
        return
    
    # Ensure data types
    data = data.copy()
    data['report_date'] = pd.to_datetime(data['report_date'], errors='coerce')
    numeric_cols = ['cost', 'gross_revenue', 'orders_(sku)', 'roi']
    for col in numeric_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
    
    # Add week and month columns
    data['week'] = data['report_date'].dt.to_period('W').apply(lambda x: x.start_time)
    data['month'] = data['report_date'].dt.to_period('M').apply(lambda x: x.start_time)
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Week over Week", "📈 Month over Month", "🔥 Top Performers", "📉 Declining Campaigns"])
    
    with tab1:
        render_week_over_week(data)
    
    with tab2:
        render_month_over_month(data)
    
    with tab3:
        render_top_performers(data)
    
    with tab4:
        render_declining_campaigns(data)

def render_week_over_week(data):
    """Render week-over-week performance comparison."""
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Metric selector
        metric = st.selectbox(
            "Select Metric",
            ["gross_revenue", "cost", "orders_(sku)", "roi"],
            format_func=lambda x: {
                "gross_revenue": "Revenue",
                "cost": "Spend",
                "orders_(sku)": "Orders",
                "roi": "ROI"
            }.get(x, x),
            key="wow_metric"
        )
        
        # Top N selector
        top_n = st.slider("Top N Campaigns", 5, 20, 10, key="wow_top_n")
    
    # Get last 4 weeks of data
    latest_date = data['report_date'].max()
    four_weeks_ago = latest_date - timedelta(weeks=4)
    recent_data = data[data['report_date'] >= four_weeks_ago]
    
    # Calculate weekly aggregates by campaign
    weekly_performance = recent_data.groupby(['week', 'campaign_name']).agg({
        metric: 'sum',
        'campaign_id': 'first'
    }).reset_index()
    
    # Get the last two complete weeks
    unique_weeks = sorted(weekly_performance['week'].unique())
    if len(unique_weeks) >= 2:
        current_week = unique_weeks[-1]
        previous_week = unique_weeks[-2]
        
        # Calculate WoW change
        current_week_data = weekly_performance[weekly_performance['week'] == current_week]
        previous_week_data = weekly_performance[weekly_performance['week'] == previous_week]
        
        # Merge to calculate changes
        wow_comparison = pd.merge(
            current_week_data[['campaign_name', metric]],
            previous_week_data[['campaign_name', metric]],
            on='campaign_name',
            suffixes=('_current', '_previous'),
            how='outer'
        ).fillna(0)
        
        # Calculate percentage change
        wow_comparison['change'] = wow_comparison[f'{metric}_current'] - wow_comparison[f'{metric}_previous']
        wow_comparison['change_pct'] = ((wow_comparison[f'{metric}_current'] / wow_comparison[f'{metric}_previous']) - 1) * 100
        wow_comparison['change_pct'] = wow_comparison['change_pct'].replace([float('inf'), -float('inf')], 0)
        
        # Sort by current week performance
        wow_comparison = wow_comparison.sort_values(f'{metric}_current', ascending=False).head(top_n)
        
        with col2:
            st.markdown(f"### Week-over-Week Change ({current_week.strftime('%b %d')} vs {previous_week.strftime('%b %d')})")
            
            # Display metrics with sparklines
            for _, row in wow_comparison.iterrows():
                campaign = row['campaign_name']
                current_val = row[f'{metric}_current']
                change_pct = row['change_pct']
                
                # Get historical data for this campaign
                campaign_history = weekly_performance[weekly_performance['campaign_name'] == campaign].sort_values('week')
                
                col_name, col_metric, col_chart = st.columns([2, 1, 2])
                
                with col_name:
                    st.markdown(f"**{campaign[:30]}...**" if len(campaign) > 30 else f"**{campaign}**")
                
                with col_metric:
                    if metric in ['gross_revenue', 'cost']:
                        display_val = f"${current_val:,.0f}"
                    elif metric == 'roi':
                        display_val = f"{current_val:.2f}x"
                    else:
                        display_val = f"{current_val:,.0f}"
                    
                    delta_color = "normal" if change_pct >= 0 else "inverse"
                    st.metric("Current", display_val, f"{change_pct:+.1f}%", delta_color=delta_color)
                
                with col_chart:
                    # Create mini chart
                    if len(campaign_history) > 1:
                        chart = alt.Chart(campaign_history).mark_line(
                            point=alt.OverlayMarkDef(size=50)
                        ).encode(
                            x=alt.X('week:T', axis=alt.Axis(format='%b %d', title=None)),
                            y=alt.Y(f'{metric}:Q', axis=alt.Axis(title=None)),
                            tooltip=[
                                alt.Tooltip('week:T', format='%b %d', title='Week'),
                                alt.Tooltip(f'{metric}:Q', format=',.0f', title=metric.replace('_', ' ').title())
                            ]
                        ).properties(height=80)
                        st.altair_chart(chart, use_container_width=True)

def render_month_over_month(data):
    """Render month-over-month performance comparison."""
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Metric selector
        metric = st.selectbox(
            "Select Metric",
            ["gross_revenue", "cost", "orders_(sku)", "roi"],
            format_func=lambda x: {
                "gross_revenue": "Revenue",
                "cost": "Spend", 
                "orders_(sku)": "Orders",
                "roi": "ROI"
            }.get(x, x),
            key="mom_metric"
        )
        
        # Top N selector
        top_n = st.slider("Top N Campaigns", 5, 20, 10, key="mom_top_n")
    
    # Calculate monthly aggregates by campaign
    monthly_performance = data.groupby(['month', 'campaign_name']).agg({
        metric: 'sum',
        'campaign_id': 'first'
    }).reset_index()
    
    # Get the last two complete months
    unique_months = sorted(monthly_performance['month'].unique())
    if len(unique_months) >= 2:
        current_month = unique_months[-1]
        previous_month = unique_months[-2]
        
        # Calculate MoM change
        current_month_data = monthly_performance[monthly_performance['month'] == current_month]
        previous_month_data = monthly_performance[monthly_performance['month'] == previous_month]
        
        # Merge to calculate changes
        mom_comparison = pd.merge(
            current_month_data[['campaign_name', metric]],
            previous_month_data[['campaign_name', metric]],
            on='campaign_name',
            suffixes=('_current', '_previous'),
            how='outer'
        ).fillna(0)
        
        # Calculate percentage change
        mom_comparison['change'] = mom_comparison[f'{metric}_current'] - mom_comparison[f'{metric}_previous']
        mom_comparison['change_pct'] = ((mom_comparison[f'{metric}_current'] / mom_comparison[f'{metric}_previous']) - 1) * 100
        mom_comparison['change_pct'] = mom_comparison['change_pct'].replace([float('inf'), -float('inf')], 0)
        
        # Sort by current month performance
        mom_comparison = mom_comparison.sort_values(f'{metric}_current', ascending=False).head(top_n)
        
        with col2:
            st.markdown(f"### Month-over-Month Change ({current_month.strftime('%B')} vs {previous_month.strftime('%B')})")
            
            # Create bar chart comparison
            chart_data = []
            for _, row in mom_comparison.iterrows():
                campaign_name = row['campaign_name'][:20] + '...' if len(row['campaign_name']) > 20 else row['campaign_name']
                chart_data.append({
                    'Campaign': campaign_name,
                    'Period': previous_month.strftime('%B'),
                    'Value': row[f'{metric}_previous']
                })
                chart_data.append({
                    'Campaign': campaign_name,
                    'Period': current_month.strftime('%B'),
                    'Value': row[f'{metric}_current']
                })
            
            chart_df = pd.DataFrame(chart_data)
            
            # Create grouped bar chart
            chart = alt.Chart(chart_df).mark_bar().encode(
                x=alt.X('Campaign:N', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Value:Q', axis=alt.Axis(title=metric.replace('_', ' ').title())),
                color=alt.Color('Period:N', scale=alt.Scale(scheme='category10')),
                xOffset='Period:N',
                tooltip=[
                    alt.Tooltip('Campaign:N'),
                    alt.Tooltip('Period:N'),
                    alt.Tooltip('Value:Q', format=',.0f')
                ]
            ).properties(height=400)
            
            st.altair_chart(chart, use_container_width=True)
            
            # Show detailed table
            st.markdown("#### Detailed Comparison")
            display_df = mom_comparison.copy()
            display_df = display_df.rename(columns={
                f'{metric}_current': current_month.strftime('%B'),
                f'{metric}_previous': previous_month.strftime('%B'),
                'change': 'Change',
                'change_pct': 'Change %'
            })
            display_df = display_df[['campaign_name', previous_month.strftime('%B'), 
                                     current_month.strftime('%B'), 'Change', 'Change %']]
            display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.1f}%")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)

def render_top_performers(data):
    """Identify and display top performing campaigns."""
    
    # Get last 30 days of data
    latest_date = data['report_date'].max()
    thirty_days_ago = latest_date - timedelta(days=30)
    recent_data = data[data['report_date'] >= thirty_days_ago]
    
    if recent_data.empty:
        st.warning("No recent data available")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏆 Top by Revenue")
        top_revenue = recent_data.groupby('campaign_name').agg({
            'gross_revenue': 'sum',
            'cost': 'sum',
            'orders_(sku)': 'sum'
        }).sort_values('gross_revenue', ascending=False).head(10)
        
        top_revenue['ROI'] = (top_revenue['gross_revenue'] / top_revenue['cost']).round(2)
        top_revenue = top_revenue.rename(columns={
            'gross_revenue': 'Revenue',
            'cost': 'Spend',
            'orders_(sku)': 'Orders'
        })
        
        # Format currency columns
        for col in ['Revenue', 'Spend']:
            top_revenue[col] = top_revenue[col].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(top_revenue, use_container_width=True)
    
    with col2:
        st.markdown("### 💰 Top by ROI")
        # Filter for campaigns with minimum spend
        min_spend = recent_data['cost'].quantile(0.25)  # At least 25th percentile spend
        qualified_campaigns = recent_data[recent_data['cost'] >= min_spend]
        
        top_roi = qualified_campaigns.groupby('campaign_name').agg({
            'gross_revenue': 'sum',
            'cost': 'sum',
            'orders_(sku)': 'sum'
        })
        top_roi['ROI'] = (top_roi['gross_revenue'] / top_roi['cost']).round(2)
        top_roi = top_roi.sort_values('ROI', ascending=False).head(10)
        
        top_roi = top_roi.rename(columns={
            'gross_revenue': 'Revenue',
            'cost': 'Spend',
            'orders_(sku)': 'Orders'
        })
        
        # Format currency columns
        for col in ['Revenue', 'Spend']:
            top_roi[col] = top_roi[col].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(top_roi, use_container_width=True)

def render_declining_campaigns(data):
    """Identify campaigns with declining performance."""
    
    # Get last 4 weeks of data
    latest_date = data['report_date'].max()
    four_weeks_ago = latest_date - timedelta(weeks=4)
    recent_data = data[data['report_date'] >= four_weeks_ago]
    
    # Split into two periods
    midpoint = latest_date - timedelta(weeks=2)
    first_half = recent_data[recent_data['report_date'] < midpoint]
    second_half = recent_data[recent_data['report_date'] >= midpoint]
    
    if first_half.empty or second_half.empty:
        st.warning("Not enough data for trend analysis")
        return
    
    # Calculate performance for each period
    first_period = first_half.groupby('campaign_name').agg({
        'gross_revenue': 'sum',
        'cost': 'sum',
        'orders_(sku)': 'sum'
    })
    
    second_period = second_half.groupby('campaign_name').agg({
        'gross_revenue': 'sum',
        'cost': 'sum',
        'orders_(sku)': 'sum'
    })
    
    # Compare periods
    comparison = pd.merge(
        first_period,
        second_period,
        left_index=True,
        right_index=True,
        suffixes=('_first', '_second'),
        how='inner'
    )
    
    # Calculate decline percentage
    comparison['revenue_change'] = ((comparison['gross_revenue_second'] / comparison['gross_revenue_first']) - 1) * 100
    comparison['orders_change'] = ((comparison['orders_(sku)_second'] / comparison['orders_(sku)_first']) - 1) * 100
    
    # Filter for declining campaigns (at least 20% decline)
    declining = comparison[
        (comparison['revenue_change'] < -20) | 
        (comparison['orders_change'] < -20)
    ].sort_values('revenue_change')
    
    if declining.empty:
        st.success("✅ No significantly declining campaigns detected!")
    else:
        st.markdown("### ⚠️ Campaigns Needing Attention")
        st.markdown("*Campaigns with >20% decline in last 2 weeks*")
        
        display_df = declining.copy()
        display_df['Revenue Change'] = display_df['revenue_change'].apply(lambda x: f"{x:+.1f}%")
        display_df['Orders Change'] = display_df['orders_change'].apply(lambda x: f"{x:+.1f}%")
        display_df['Current Revenue'] = display_df['gross_revenue_second'].apply(lambda x: f"${x:,.0f}")
        display_df['Previous Revenue'] = display_df['gross_revenue_first'].apply(lambda x: f"${x:,.0f}")
        
        display_df = display_df[['Previous Revenue', 'Current Revenue', 'Revenue Change', 'Orders Change']]
        
        st.dataframe(display_df, use_container_width=True)