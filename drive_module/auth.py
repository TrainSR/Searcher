import os
import toml  # pip install toml nếu chưa có
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_drive_service():
    credentials = None

    # 1. Ưu tiên: Đọc secrets từ drive_module/secrets.toml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_secrets_path = os.path.join(current_dir, "secrets.toml")

    if os.path.exists(local_secrets_path):
        try:
            config = toml.load(local_secrets_path)
            creds_dict = config.get("gcp_service_account")
            if creds_dict:
                credentials = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            raise RuntimeError(f"Lỗi khi đọc local secrets.toml: {e}")

    # 2. Nếu không có local secrets → thử Streamlit secrets
    if credentials is None:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            raise RuntimeError(
                "Không tìm thấy credentials trong local secrets.toml hoặc st.secrets.\n"
                f"Chi tiết: {e}"
            )

    return build("drive", "v3", credentials=credentials)
