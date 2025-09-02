import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timedelta
import json

# Configure Gemini AI
def configure_gemini(api_key):
    """Configure Gemini AI with the provided API key."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

def prepare_data_context(data):
    """Prepare data context for AI analysis."""
    if data.empty:
        return None
    
    # Calculate key metrics
    total_cost = data['cost'].sum() if 'cost' in data.columns else 0
    total_revenue = data['gross_revenue'].sum() if 'gross_revenue' in data.columns else 0
    total_orders = data['orders_(sku)'].sum() if 'orders_(sku)' in data.columns else 0
    overall_roi = (total_revenue / total_cost) if total_cost > 0 else 0
    
    # Get date range
    date_range = f"{data['report_date'].min().strftime('%Y-%m-%d')} to {data['report_date'].max().strftime('%Y-%m-%d')}"
    
    # Top campaigns by revenue
    top_campaigns = data.groupby('campaign_name').agg({
        'gross_revenue': 'sum',
        'cost': 'sum',
        'orders_(sku)': 'sum'
    }).sort_values('gross_revenue', ascending=False).head(5)
    
    # Convert to serializable format
    top_campaigns_dict = {}
    for campaign, row in top_campaigns.iterrows():
        top_campaigns_dict[campaign] = {
            'revenue': float(row['gross_revenue']),
            'cost': float(row['cost']),
            'orders': float(row['orders_(sku)'])
        }
    
    # Account performance
    account_performance = None
    if 'account_name' in data.columns:
        account_perf = data.groupby('account_name').agg({
            'gross_revenue': 'sum',
            'cost': 'sum',
            'orders_(sku)': 'sum'
        })
        account_performance = {}
        for account, row in account_perf.iterrows():
            account_performance[account] = {
                'revenue': float(row['gross_revenue']),
                'cost': float(row['cost']),
                'orders': float(row['orders_(sku)'])
            }
    
    # Recent trends (last 7 days vs previous 7 days)
    latest_date = data['report_date'].max()
    week_ago = latest_date - timedelta(days=7)
    two_weeks_ago = latest_date - timedelta(days=14)
    
    recent_week = data[data['report_date'] > week_ago]
    previous_week = data[(data['report_date'] > two_weeks_ago) & (data['report_date'] <= week_ago)]
    
    recent_metrics = {
        'cost': recent_week['cost'].sum() if not recent_week.empty else 0,
        'revenue': recent_week['gross_revenue'].sum() if not recent_week.empty else 0,
        'orders': recent_week['orders_(sku)'].sum() if not recent_week.empty else 0
    }
    
    previous_metrics = {
        'cost': previous_week['cost'].sum() if not previous_week.empty else 0,
        'revenue': previous_week['gross_revenue'].sum() if not previous_week.empty else 0,
        'orders': previous_week['orders_(sku)'].sum() if not previous_week.empty else 0
    }
    
    context = {
        'date_range': date_range,
        'total_campaigns': data['campaign_name'].nunique(),
        'total_cost': f"${total_cost:,.2f}",
        'total_revenue': f"${total_revenue:,.2f}",
        'total_orders': f"{total_orders:,.0f}",
        'overall_roi': f"{overall_roi:.2f}x",
        'top_campaigns': top_campaigns_dict,
        'account_performance': account_performance,
        'recent_week_metrics': recent_metrics,
        'previous_week_metrics': previous_metrics,
        'week_over_week_changes': {
            'cost_change': ((recent_metrics['cost'] / previous_metrics['cost']) - 1) * 100 if previous_metrics['cost'] > 0 else 0,
            'revenue_change': ((recent_metrics['revenue'] / previous_metrics['revenue']) - 1) * 100 if previous_metrics['revenue'] > 0 else 0,
            'orders_change': ((recent_metrics['orders'] / previous_metrics['orders']) - 1) * 100 if previous_metrics['orders'] > 0 else 0,
        }
    }
    
    return context

def generate_executive_summary(model, context):
    """Generate executive summary using Gemini AI."""
    prompt = f"""
    You are an expert digital marketing analyst specializing in TikTok advertising campaigns for consumer products.
    
    Based on the following advertising data, provide an encouraging and constructive executive summary (3-4 paragraphs) that:
    1. Analyzes the campaign names to understand the product portfolio
    2. Highlights the strongest performing products and celebrates successes
    3. Considers seasonality based on product types identified from campaign names
    4. Identifies cross-selling opportunities between complementary products
    5. Maintains a positive, forward-looking tone while providing constructive suggestions
    
    Data Context:
    - Date Range: {context['date_range']}
    - Total Campaigns: {context['total_campaigns']}
    - Total Spend: {context['total_cost']}
    - Total Revenue: {context['total_revenue']}
    - Total Orders: {context['total_orders']}
    - Overall ROI: {context['overall_roi']}
    
    Week-over-Week Changes:
    - Cost: {context['week_over_week_changes']['cost_change']:.1f}%
    - Revenue: {context['week_over_week_changes']['revenue_change']:.1f}%
    - Orders: {context['week_over_week_changes']['orders_change']:.1f}%
    
    Top Campaigns (campaign names ARE the branded product names):
    {json.dumps(context['top_campaigns'], indent=2, default=str)}
    
    IMPORTANT: Analyze each campaign name to determine:
    - What type of product it is (cookware, appliance, gadget, etc.)
    - Its likely function and target audience
    - Seasonal relevance (grilling products for summer, baking for holidays, etc.)
    
    Remember to:
    - Identify product categories from the campaign names
    - Consider how different product types have different seasonal patterns
    - Suggest bundle opportunities between complementary products
    - Lead with positives and successful outcomes
    - Provide specific, actionable recommendations based on product types
    
    Format the response in clear, encouraging paragraphs with no bullet points or markdown formatting.
    """
    
    try:
        response = model.generate_content(prompt)
        # Escape dollar signs to prevent LaTeX interpretation
        text = response.text.replace('$', '\\$')
        return text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def generate_all_campaigns_breakdown(model, data):
    """Generate a comprehensive breakdown of all campaigns."""
    # Calculate metrics for each campaign
    campaigns_data = []
    for campaign in data['campaign_name'].unique():
        campaign_data = data[data['campaign_name'] == campaign]
        
        metrics = {
            'name': campaign,
            'spend': float(campaign_data['cost'].sum()),
            'revenue': float(campaign_data['gross_revenue'].sum()),
            'orders': float(campaign_data['orders_(sku)'].sum()),
            'roi': float(campaign_data['gross_revenue'].sum() / campaign_data['cost'].sum()) if campaign_data['cost'].sum() > 0 else 0,
            'days_active': campaign_data['report_date'].nunique(),
            'avg_daily_spend': float(campaign_data['cost'].sum() / campaign_data['report_date'].nunique()),
            'avg_daily_revenue': float(campaign_data['gross_revenue'].sum() / campaign_data['report_date'].nunique())
        }
        campaigns_data.append(metrics)
    
    # Sort campaigns by revenue
    campaigns_data = sorted(campaigns_data, key=lambda x: x['revenue'], reverse=True)
    
    # Categorize campaigns
    total_revenue = sum(c['revenue'] for c in campaigns_data)
    major_campaigns = [c for c in campaigns_data if c['revenue'] > total_revenue * 0.05]  # >5% of total revenue
    minor_campaigns = [c for c in campaigns_data if c['revenue'] <= total_revenue * 0.05]
    
    prompt = f"""
    Provide a comprehensive, encouraging campaign-by-campaign breakdown for this TikTok advertising portfolio:
    
    Total Campaigns: {len(campaigns_data)}
    Major Campaigns (>5% of revenue): {len(major_campaigns)}
    Supplementary Campaigns: {len(minor_campaigns)}
    
    MAJOR CAMPAIGNS DATA:
    {json.dumps(major_campaigns[:10], indent=2)}  # Top 10 major campaigns
    
    SUPPLEMENTARY CAMPAIGNS SUMMARY:
    Total Count: {len(minor_campaigns)}
    Combined Spend: ${sum(c['spend'] for c in minor_campaigns):,.2f}
    Combined Revenue: ${sum(c['revenue'] for c in minor_campaigns):,.2f}
    
    IMPORTANT: Campaign names contain the actual branded product names. Please analyze each campaign name to:
    - Identify what type of product it is (kitchen gadget, cookware, appliance, etc.)
    - Infer the product's function/purpose from its name
    - Consider appropriate seasonality and use cases for that product type
    
    For example:
    - "Granitestone" suggests non-stick cookware
    - "RiceRobot" indicates an automated rice cooker
    - "Piezano" might be a pizza-related cooking product
    
    Please provide:
    1. A BRIEF overview paragraph celebrating overall portfolio performance
    2. DETAILED analysis of each MAJOR campaign (focus on top 5-7):
       - Identify the product type and likely function based on the name
       - What's working well for this product category
       - Consider seasonality for this specific product type
       - Target audience insights based on product type
       - Growth opportunities specific to this product's market
    3. A BRIEF summary of supplementary campaigns as a group
    4. Strategic recommendations considering the product mix
    
    Remember to:
    - Analyze product names to understand what each product does
    - Consider how different product categories perform differently
    - Think about seasonal relevance (grilling products for summer, baking for holidays, etc.)
    - Suggest cross-promotion opportunities between complementary products
    - Be encouraging and frame improvements as opportunities
    
    Format as clear paragraphs with campaign/product names in bold. Avoid bullet points.
    """
    
    try:
        response = model.generate_content(prompt)
        # Escape dollar signs to prevent LaTeX interpretation
        text = response.text.replace('$', '\\$')
        return text
    except Exception as e:
        return f"Error generating breakdown: {str(e)}"

def generate_campaign_insights(model, data, campaign_name):
    """Generate specific insights for a campaign."""
    campaign_data = data[data['campaign_name'] == campaign_name]
    
    if campaign_data.empty:
        return "No data available for this campaign."
    
    # Calculate campaign metrics
    metrics = {
        'total_cost': campaign_data['cost'].sum(),
        'total_revenue': campaign_data['gross_revenue'].sum(),
        'total_orders': campaign_data['orders_(sku)'].sum(),
        'roi': (campaign_data['gross_revenue'].sum() / campaign_data['cost'].sum()) if campaign_data['cost'].sum() > 0 else 0,
        'avg_cost_per_order': campaign_data['cost'].sum() / campaign_data['orders_(sku)'].sum() if campaign_data['orders_(sku)'].sum() > 0 else 0,
        'date_range': f"{campaign_data['report_date'].min().strftime('%Y-%m-%d')} to {campaign_data['report_date'].max().strftime('%Y-%m-%d')}",
        'days_active': campaign_data['report_date'].nunique()
    }
    
    # Daily performance trends
    daily_performance = campaign_data.groupby('report_date').agg({
        'cost': 'sum',
        'gross_revenue': 'sum',
        'orders_(sku)': 'sum'
    }).tail(7)
    
    # Convert to dictionary with string dates
    daily_performance_dict = {}
    for date, row in daily_performance.iterrows():
        daily_performance_dict[date.strftime('%Y-%m-%d')] = {
            'cost': float(row['cost']),
            'revenue': float(row['gross_revenue']),
            'orders': float(row['orders_(sku)'])
        }
    
    prompt = f"""
    Analyze this TikTok advertising campaign with a constructive and encouraging perspective:
    
    Campaign: {campaign_name}
    
    FIRST, analyze the campaign name to determine:
    - What type of product this is (the campaign name IS the branded product name)
    - What the product likely does/its primary function
    - Who the target audience might be for this product
    
    Overall Metrics:
    - Total Spend: ${metrics['total_cost']:,.2f}
    - Total Revenue: ${metrics['total_revenue']:,.2f}
    - Total Orders: {metrics['total_orders']:,.0f}
    - ROI: {metrics['roi']:.2f}x
    - Average Cost per Order: ${metrics['avg_cost_per_order']:,.2f}
    - Date Range: {metrics['date_range']}
    - Days Active: {metrics['days_active']}
    
    Recent Daily Performance (Last 7 days):
    {json.dumps(daily_performance_dict, indent=2)}
    
    Please provide a positive and constructive analysis that:
    1. Identifies the product type and function based on its name
    2. Celebrates what's working well for this specific product type
    3. Considers seasonality and optimal selling periods for this product
    4. Suggests marketing angles based on the product's function
    5. Identifies growth opportunities specific to this product category
    
    Consider factors like:
    - Is this a seasonal product? (grilling, holiday baking, etc.)
    - What problems does this product solve?
    - What demographic would be most interested?
    - What time of year would demand be highest?
    - What complementary products from the portfolio could cross-sell?
    
    Keep the response encouraging, concise (2-3 paragraphs) and actionable.
    """
    
    try:
        response = model.generate_content(prompt)
        # Escape dollar signs to prevent LaTeX interpretation
        text = response.text.replace('$', '\\$')
        return text
    except Exception as e:
        return f"Error generating insights: {str(e)}"

def generate_anomaly_detection(model, data):
    """Detect anomalies and unusual patterns in the data."""
    # Calculate daily aggregates
    daily_data = data.groupby('report_date').agg({
        'cost': 'sum',
        'gross_revenue': 'sum',
        'orders_(sku)': 'sum',
        'campaign_name': 'count'
    }).reset_index()
    
    daily_data['roi'] = daily_data['gross_revenue'] / daily_data['cost']
    
    # Calculate statistics
    stats = {
        'avg_daily_cost': daily_data['cost'].mean(),
        'std_daily_cost': daily_data['cost'].std(),
        'avg_daily_revenue': daily_data['gross_revenue'].mean(),
        'std_daily_revenue': daily_data['gross_revenue'].std(),
        'avg_roi': daily_data['roi'].mean(),
        'std_roi': daily_data['roi'].std()
    }
    
    # Find anomalies (days with metrics > 2 std deviations from mean)
    anomalies = []
    for _, row in daily_data.iterrows():
        if abs(row['cost'] - stats['avg_daily_cost']) > 2 * stats['std_daily_cost']:
            anomalies.append({
                'date': row['report_date'].strftime('%Y-%m-%d'),
                'type': 'cost',
                'value': row['cost'],
                'deviation': (row['cost'] - stats['avg_daily_cost']) / stats['std_daily_cost']
            })
        if abs(row['gross_revenue'] - stats['avg_daily_revenue']) > 2 * stats['std_daily_revenue']:
            anomalies.append({
                'date': row['report_date'].strftime('%Y-%m-%d'),
                'type': 'revenue',
                'value': row['gross_revenue'],
                'deviation': (row['gross_revenue'] - stats['avg_daily_revenue']) / stats['std_daily_revenue']
            })
    
    if not anomalies:
        return "No significant anomalies detected in the recent data."
    
    prompt = f"""
    Analyze these notable patterns in TikTok advertising data with a positive, constructive perspective:
    
    Daily Statistics:
    - Average Daily Cost: ${stats['avg_daily_cost']:,.2f}
    - Average Daily Revenue: ${stats['avg_daily_revenue']:,.2f}
    - Average ROI: {stats['avg_roi']:.2f}x
    
    Notable Variations Detected (significant changes from average):
    {json.dumps(anomalies, indent=2)}
    
    Please provide an encouraging analysis that:
    1. Frames these variations as opportunities or successes where appropriate
    2. Considers positive causes (successful promotions, seasonal peaks, viral content)
    3. Suggests constructive actions to capitalize on positive trends
    4. Acknowledges that variations can be normal and healthy for campaigns
    
    Remember:
    - Spikes might indicate successful campaign moments to replicate
    - Dips might be normal seasonal patterns or opportunities to test new approaches
    - Consider product seasonality based on campaign names
    - Keep the tone optimistic and action-oriented
    
    Be concise, practical, and encouraging in your analysis.
    """
    
    try:
        response = model.generate_content(prompt)
        # Escape dollar signs to prevent LaTeX interpretation
        text = response.text.replace('$', '\\$')
        return text
    except Exception as e:
        return f"Error detecting anomalies: {str(e)}"

def render_ai_insights(data, api_key):
    """Main function to render AI insights section."""
    st.markdown("## 🤖 AI-Powered Insights")
    
    if not api_key:
        st.warning("⚠️ Gemini API key not configured. Add GEMINI_API_KEY to your environment or secrets.")
        return
    
    # Configure Gemini
    try:
        model = configure_gemini(api_key)
    except Exception as e:
        st.error(f"Failed to configure Gemini AI: {str(e)}")
        return
    
    # Prepare data context
    context = prepare_data_context(data)
    if not context:
        st.warning("Insufficient data for AI analysis.")
        return
    
    # Create tabs for different AI insights
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Executive Summary", 
        "🎯 Campaign Analysis", 
        "🔍 Anomaly Detection",
        "💡 Custom Query"
    ])
    
    with tab1:
        st.markdown("### Executive Summary")
        st.markdown("*AI-generated overview of your advertising performance*")
        
        if st.button("🔄 Generate Summary", key="generate_summary"):
            with st.spinner("Analyzing data and generating insights..."):
                summary = generate_executive_summary(model, context)
                st.markdown(summary)
                
                # Option to regenerate
                if st.button("🔄 Regenerate with different perspective", key="regenerate_summary"):
                    with st.spinner("Generating alternative analysis..."):
                        # Add variation to prompt
                        context['analysis_focus'] = 'cost_efficiency'
                        summary = generate_executive_summary(model, context)
                        st.markdown(summary)
    
    with tab2:
        st.markdown("### Campaign Analysis")
        st.markdown("*Comprehensive breakdown of all campaigns or individual deep-dive*")
        
        analysis_type = st.radio(
            "Analysis Type:",
            ["📊 All Campaigns Breakdown", "🔍 Individual Campaign Deep-Dive"],
            key="analysis_type"
        )
        
        if analysis_type == "📊 All Campaigns Breakdown":
            if st.button("📋 Generate Full Campaign Breakdown", key="analyze_all_campaigns"):
                with st.spinner("Analyzing all campaigns..."):
                    breakdown = generate_all_campaigns_breakdown(model, data)
                    st.markdown(breakdown)
                    
                    # Also show a summary table
                    st.markdown("#### Campaign Performance Summary")
                    campaign_summary = data.groupby('campaign_name').agg({
                        'cost': 'sum',
                        'gross_revenue': 'sum',
                        'orders_(sku)': 'sum'
                    }).round(2)
                    campaign_summary['ROI'] = (campaign_summary['gross_revenue'] / campaign_summary['cost']).round(2)
                    campaign_summary['Cost per Order'] = (campaign_summary['cost'] / campaign_summary['orders_(sku)']).round(2)
                    
                    # Format currency columns
                    campaign_summary['cost'] = campaign_summary['cost'].apply(lambda x: f"${x:,.0f}")
                    campaign_summary['gross_revenue'] = campaign_summary['gross_revenue'].apply(lambda x: f"${x:,.0f}")
                    campaign_summary['orders_(sku)'] = campaign_summary['orders_(sku)'].apply(lambda x: f"{x:,.0f}")
                    campaign_summary['Cost per Order'] = campaign_summary['Cost per Order'].apply(lambda x: f"${x:,.2f}")
                    
                    st.dataframe(
                        campaign_summary.sort_values('ROI', ascending=False),
                        use_container_width=True
                    )
        else:
            # Campaign selector for individual analysis
            campaign_list = data['campaign_name'].unique().tolist()
            selected_campaign = st.selectbox(
                "Select a campaign to analyze:",
                campaign_list,
                key="campaign_selector"
            )
            
            if st.button("🔍 Analyze Campaign", key="analyze_campaign"):
                with st.spinner(f"Analyzing {selected_campaign}..."):
                    insights = generate_campaign_insights(model, data, selected_campaign)
                    st.markdown(insights)
    
    with tab3:
        st.markdown("### Anomaly Detection")
        st.markdown("*Identify unusual patterns and outliers in your data*")
        
        if st.button("🔍 Detect Anomalies", key="detect_anomalies"):
            with st.spinner("Scanning for anomalies..."):
                anomaly_report = generate_anomaly_detection(model, data)
                st.markdown(anomaly_report)
    
    with tab4:
        st.markdown("### Custom Analysis Query")
        st.markdown("*Ask specific questions about your advertising data*")
        
        custom_query = st.text_area(
            "Enter your question:",
            placeholder="e.g., Which campaigns should I increase budget for? What's driving the decline in ROI? How can I improve cost per acquisition?",
            height=100,
            key="custom_query"
        )
        
        if st.button("🤔 Get AI Analysis", key="analyze_custom"):
            if custom_query:
                with st.spinner("Analyzing your question..."):
                    # Create custom prompt with data context
                    custom_prompt = f"""
                    Based on this TikTok advertising data, answer the following question with an encouraging and constructive perspective:
                    
                    Question: {custom_query}
                    
                    Data Summary:
                    - Date Range: {context['date_range']}
                    - Total Spend: {context['total_cost']}
                    - Total Revenue: {context['total_revenue']}
                    - Overall ROI: {context['overall_roi']}
                    - Total Campaigns: {context['total_campaigns']}
                    
                    Top Campaigns (Product-named):
                    {json.dumps(context['top_campaigns'], indent=2, default=str)}
                    
                    Recent Performance Trends:
                    - Week-over-week cost change: {context['week_over_week_changes']['cost_change']:.1f}%
                    - Week-over-week revenue change: {context['week_over_week_changes']['revenue_change']:.1f}%
                    
                    Please provide a positive, constructive answer that:
                    - Highlights successes and strengths first
                    - Considers product seasonality based on campaign names
                    - Frames suggestions as opportunities for growth
                    - Acknowledges the difference between major and supplementary campaigns
                    - Maintains an encouraging, forward-looking tone
                    
                    Provide specific, actionable recommendations with an optimistic outlook.
                    """
                    
                    try:
                        response = model.generate_content(custom_prompt)
                        # Escape dollar signs to prevent LaTeX interpretation
                        text = response.text.replace('$', '\\$')
                        st.markdown(text)
                    except Exception as e:
                        st.error(f"Error generating response: {str(e)}")
            else:
                st.warning("Please enter a question to analyze.")
    
    # Add export functionality for AI insights
    st.markdown("---")
    st.markdown("### 💾 Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Generate Full Report", key="generate_full_report"):
            with st.spinner("Generating comprehensive report..."):
                full_report = {
                    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'executive_summary': generate_executive_summary(model, context),
                    'anomalies': generate_anomaly_detection(model, data),
                    'data_context': context
                }
                
                st.download_button(
                    label="📥 Download AI Report (JSON)",
                    data=json.dumps(full_report, indent=2, default=str),
                    file_name=f"ai_insights_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )