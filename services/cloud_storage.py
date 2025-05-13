import io
import os
import uuid
import streamlit as st
from google.cloud import storage

def upload_excel_to_gcs(excel_bytes, bucket_name, credentials_dict, original_filename="report.xlsx"):
    """Uploads an Excel file (in bytes) to Google Cloud Storage."""
    try:
        buffer = io.BytesIO(excel_bytes)
        buffer.seek(0)

        # Create a unique filename, perhaps incorporating the original name
        base, ext = os.path.splitext(original_filename)
        filename = f"reports/{base}_{uuid.uuid4().hex}{ext}"

        # Init GCS client
        client = storage.Client.from_service_account_info(credentials_dict)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Construct the public URL manually for uniform bucket-level access
        public_url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
        return public_url
    except Exception as e:
        st.error(f"Error uploading Excel to GCS: {e}")
        return None

def upload_chart_to_gcs(chart, bucket_name, credentials_dict):
    """Uploads an Altair chart image to Google Cloud Storage."""
    try:
        # Convert chart to PNG in memory
        buffer = io.BytesIO()
        # Ensure chart object is valid before saving
        if chart is None:
            st.error("Chart object is None, cannot upload.")
            return None
        chart.save(buffer, format='png', scale_factor=2.0)
        buffer.seek(0)

        # Create a unique filename
        filename = f"charts/chart_{uuid.uuid4().hex}.png"

        # Init GCS client
        client = storage.Client.from_service_account_info(credentials_dict)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(buffer, content_type='image/png')

        # Construct the public URL manually for uniform bucket-level access
        public_url = f"https://storage.googleapis.com/{bucket.name}/{blob.name}"
        return public_url
    except Exception as e:
        st.error(f"Error uploading chart to GCS: {e}")
        return None