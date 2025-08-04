#auth.py

import os
import toml  # pip install toml nếu chưa có
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
def load_secret_value(section: str, key: str):
    """
    Trả về giá trị từ một mục bất kỳ trong secrets.toml (ưu tiên local, fallback st.secrets).
    Ví dụ: load_secret_value("gcp_service_account", "private_key")
    """
    import toml

    # Đường dẫn đến file secrets.toml (cùng thư mục với auth.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_secrets_path = os.path.join(current_dir, "secrets.toml")

    # 1. Ưu tiên đọc từ local secrets.toml
    if os.path.exists(local_secrets_path):
        try:
            config = toml.load(local_secrets_path)
            section_data = config.get(section)
            if section_data and key in section_data:
                return section_data[key]
        except Exception as e:
            raise RuntimeError(f"Lỗi khi đọc local secrets.toml: {e}")

    # 2. Nếu không có thì thử từ st.secrets
    try:
        section_data = st.secrets[section]
        if key in section_data:
            return section_data[key]
    except Exception as e:
        raise RuntimeError(f"Lỗi khi đọc st.secrets[{section}]: {e}")

    # Nếu không tìm thấy
    raise KeyError(f"Không tìm thấy [{section}][{key}] trong cả local secrets.toml và st.secrets.")


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
