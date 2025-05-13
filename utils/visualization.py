import altair as alt
import streamlit as st

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

def generate_multi_metric_line_chart(melted_df, main_metrics):
    """Generates a multi-metric line chart for the main dashboard visualization."""
    line_chart = alt.Chart(melted_df).mark_line(point=True).encode(
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
    
    return line_chart

def create_side_by_side_charts(filtered_data, metrics):
    """Creates side-by-side charts for multiple metrics."""
    metric_chunks = [metrics[i:i+2] for i in range(0, len(metrics), 2)]
    charts = []
    
    for chunk in metric_chunks:
        chunk_charts = []
        for metric in chunk:
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
                width=600,
                height=300,
                title=metric.replace("_", " ").title()
            )
            chunk_charts.append(chart)
        charts.append(chunk_charts)
    
    return charts