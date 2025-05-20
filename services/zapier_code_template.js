// Zapier JavaScript for TikTok Ad Reports Email Generator
// This script processes webhook data and generates HTML for email content

// According to Zapier docs, inputData is directly available
// and we should return an object directly

// Main function to process data and return formatted email content
function processWebhookData(inputData) {
  // For debugging
  console.log("Input data received:", Object.keys(inputData));

  // Set default values with fallbacks
  const summaryMetrics = inputData.summary_metrics || {};
  const chartImages = inputData.chart_images || {};
  const topCampaigns = Array.isArray(inputData.top_campaigns) ? inputData.top_campaigns : [];
  const remainingCampaigns = Array.isArray(inputData.remaining_campaigns) ? inputData.remaining_campaigns : [];
  const startDate = inputData.start_date || 'N/A';
  const endDate = inputData.end_date || 'N/A';
  const excelReportUrl = inputData.excel_report_url || '';
  
  // Email subject
  const emailSubject = `TikTok Ad Performance Report: ${startDate} to ${endDate}`;
  
  // Generate the email HTML content
  let emailHtml = `
    <html>
    <head>
      <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; padding: 20px 0; }
        .summary { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .summary-metrics { display: flex; flex-wrap: wrap; justify-content: space-between; }
        .metric { width: 48%; margin-bottom: 10px; }
        .metric-value { font-weight: bold; font-size: 18px; }
        .chart-section { margin: 30px 0; }
        .campaign-section { margin: 30px 0; }
        .top-campaign { background-color: #f0f2f6; border-radius: 5px; padding: 15px; margin-bottom: 15px; }
        .campaign-name { font-weight: bold; font-size: 16px; }
        .campaign-metrics { display: flex; flex-wrap: wrap; }
        .campaign-metric { width: 50%; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        img { max-width: 100%; height: auto; }
        .download-button { background-color: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 20px; }
        .footer { margin-top: 40px; text-align: center; font-size: 12px; color: #666; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>TikTok Ad Performance Report</h1>
          <p>${startDate} to ${endDate}</p>
        </div>
        
        <div class="summary">
          <h2>Summary Metrics</h2>
          <div class="summary-metrics">`;
  
  // Add summary metrics with fallbacks
  const metrics = [
    { label: "Total Cost", value: summaryMetrics.total_cost || "$0.00" },
    { label: "Total Revenue", value: summaryMetrics.total_revenue || "$0.00" },
    { label: "Total Orders", value: summaryMetrics.total_orders || "0" },
    { label: "Average ROI", value: summaryMetrics.avg_roi || "0.00x" },
    { label: "Average Cost/Order", value: summaryMetrics.avg_cost_per_order || "$0.00" }
  ];
  
  metrics.forEach(metric => {
    emailHtml += `
      <div class="metric">
        <div>${metric.label}</div>
        <div class="metric-value">${metric.value}</div>
      </div>`;
  });
  
  emailHtml += `
          </div>
        </div>
        
        <div class="chart-section">
          <h2>Performance Charts</h2>`;
  
  // Add chart images
  const chartTypes = [
    { key: "gross_revenue_url", label: "Gross Revenue" },
    { key: "cost_url", label: "Cost" },
    { key: "roi_url", label: "ROI" },
    { key: "orders_url", label: "Orders" },
    { key: "cost_per_order_url", label: "Cost Per Order" }
  ];
  
  chartTypes.forEach(chart => {
    if (chartImages[chart.key]) {
      emailHtml += `
        <div style="margin-bottom: 30px;">
          <h3>${chart.label}</h3>
          <img src="${chartImages[chart.key]}" alt="${chart.label} Chart">
        </div>`;
    }
  });
  
  emailHtml += `
        </div>
        
        <div class="campaign-section">
          <h2>Top Performing Campaigns</h2>`;
  
  // Add top campaigns
  if (topCampaigns.length > 0) {
    const medals = ["🥇", "🥈", "🥉"];
    
    topCampaigns.forEach((campaign, index) => {
      if (campaign && campaign.name) {
        const medal = index < medals.length ? medals[index] : "";
        const metrics = campaign.metrics || {};
        
        emailHtml += `
          <div class="top-campaign">
            <div class="campaign-name">${medal} ${campaign.name}</div>
            <div class="campaign-metrics">`;
        
        if (metrics.orders_formatted) {
          emailHtml += `
              <div class="campaign-metric">Orders: <strong>${metrics.orders_formatted}</strong></div>`;
        }
        
        if (metrics.cost_formatted) {
          emailHtml += `
              <div class="campaign-metric">Spend: <strong>${metrics.cost_formatted}</strong></div>`;
        }
        
        if (metrics.revenue_formatted) {
          emailHtml += `
              <div class="campaign-metric">Revenue: <strong>${metrics.revenue_formatted}</strong></div>`;
        }
        
        if (metrics.roi_formatted) {
          emailHtml += `
              <div class="campaign-metric">ROI: <strong>${metrics.roi_formatted}</strong></div>`;
        }
        
        emailHtml += `
            </div>
          </div>`;
      }
    });
  } else {
    emailHtml += `<p>No top campaign data available.</p>`;
  }
  
  // Add remaining campaigns table
  if (remainingCampaigns.length > 0) {
    emailHtml += `
        <h2>Remaining Campaigns</h2>
        <table>
          <tr>
            <th>Campaign</th>
            <th>Orders</th>
            <th>Spend</th>
            <th>Revenue</th>
            <th>ROI</th>
          </tr>`;
    
    remainingCampaigns.forEach(campaign => {
      if (campaign && campaign.name) {
        const metrics = campaign.metrics || {};
        
        emailHtml += `
          <tr>
            <td>${campaign.name}</td>
            <td>${metrics.orders_formatted || "N/A"}</td>
            <td>${metrics.cost_formatted || "N/A"}</td>
            <td>${metrics.revenue_formatted || "N/A"}</td>
            <td>${metrics.roi_formatted || "N/A"}</td>
          </tr>`;
      }
    });
    
    emailHtml += `
        </table>`;
  }
  
  // Add download link for Excel if available
  if (excelReportUrl) {
    emailHtml += `
        <div style="margin-top: 30px; text-align: center;">
          <a href="${excelReportUrl}" class="download-button" download>Download Full Report (Excel)</a>
        </div>`;
  }
  
  // Close out the HTML
  emailHtml += `
        <div class="footer">
          <p>This report was automatically generated. Please do not reply to this email.</p>
        </div>
      </div>
    </body>
    </html>`;

  return {
    email_subject: emailSubject,
    email_body: emailHtml,
    excel_download_url: excelReportUrl || "",
    debug_info: JSON.stringify({
      dataKeys: Object.keys(inputData),
      hasTopCampaigns: Array.isArray(inputData.top_campaigns),
      campaignCount: Array.isArray(inputData.top_campaigns) ? inputData.top_campaigns.length : 0
    })
  };
}

// In Zapier, the simplest approach is to have a top-level function 
// that directly returns output from processing the inputData
try {
  console.log("Starting script execution");
  return processWebhookData(inputData);
} catch (err) {
  console.log("Error occurred:", err.message);
  return {
    email_subject: "Error: TikTok Ad Report Generation Failed",
    email_body: `<p>There was an unexpected error: ${err.message}</p>`,
    excel_download_url: "",
    error_message: err.message
  };
}