import streamlit as st
import requests
import qrcode
from io import BytesIO
import time

# 🔗 Use secrets or hardcoded fallback
API_URL = st.secrets.get("API_URL", "https://taskops-one-time-file-sharing.onrender.com")

st.set_page_config(page_title="One-Time File Sharing", page_icon="📂")

st.title("📂 One-Time File Sharing")

# Upload Section
st.header("Upload a File")
uploaded_file = st.file_uploader("Choose a file", type=["txt", "pdf", "png", "jpg", "zip"])
expiry_time = st.slider("Set Expiry Time (minutes)", 10, 120, 30)  # Default 30 mins
access_limit = st.number_input("Set Max Downloads", 1, 10, 1, step=1)

upload_progress = st.empty()
download_link_placeholder = st.empty()
qr_code_placeholder = st.empty()

if uploaded_file and st.button("🚀 Upload"):
    try:
        files = {"file": uploaded_file}
        data = {"expiry_minutes": expiry_time, "access_limit": access_limit}

        upload_progress.progress(10)
        time.sleep(0.3)
        upload_progress.progress(30)

        response = requests.post(f"{API_URL}/upload", files=files, data=data, timeout=15)

        if response.status_code == 201:
            upload_progress.progress(100)
            st.success("✅ File uploaded successfully!")

            download_url = response.json().get('download_link')

            if not download_url:
                st.error("❌ Download link missing in response.")
            else:
                # Display Download Link as a Button
                with download_link_placeholder:
                    st.markdown(
                        f'<a href="{download_url}" target="_blank">'
                        f'<button style="padding:10px 15px; font-size:16px;">🔗 Download Link</button></a>',
                        unsafe_allow_html=True,
                    )

                # Generate QR Code
                qr = qrcode.make(download_url)
                qr_bytes = BytesIO()
                qr.save(qr_bytes, format="PNG")

                with qr_code_placeholder:
                    st.image(qr_bytes, caption="Scan to Download", use_column_width=False)
        else:
            upload_progress.empty()
            st.error(f"❌ Upload failed. Status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        upload_progress.empty()
        st.error(f"🚫 Failed to connect to backend:\n\n{e}")

