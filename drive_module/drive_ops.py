#drive_ops.py

import streamlit as st
import re
from .auth import get_drive_service
from googleapiclient.http import MediaIoBaseDownload
import io
import yaml

def get_or_cache_data(key, loader_func, dependencies=None):
    dep_key = f"{key}__deps"
    if key in st.session_state and dep_key in st.session_state:
        if st.session_state[dep_key] == dependencies:
            return st.session_state[key]
    data = loader_func()
    st.session_state[key] = data
    st.session_state[dep_key] = dependencies
    return data


def extract_bullet_items_from_section(file_id, section_name):
    """
    Từ một file Markdown (qua file_id), trích xuất các dòng dạng bullet point (- ...)
    trong phần tiêu đề ## {section_name}: (dòng có định dạng cụ thể).

    Trả về danh sách các dòng bullet (không xử lý thêm).
    """
    content = get_file_content(file_id)

    # Tìm phần giữa ## {section_name}: và ## tiếp theo hoặc hết file
    pattern = rf"##\s*{re.escape(section_name)}\s*:\s*(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

    if not match:
        return []

    block = match.group(1)

    # Lấy các dòng bắt đầu bằng dấu gạch đầu dòng '-'
    lines = block.strip().splitlines()
    bullet_lines = [line.strip() for line in lines if line.strip().startswith("-")]

    return bullet_lines

def extract_yaml_from_file_id(file_id):
    """
    Đọc nội dung file .md trên Google Drive bằng file_id
    và trích xuất YAML front matter nếu có.
    """
    content = get_file_content(file_id)

    match = re.search(r'^---\s*(.*?)\s*---', content, re.DOTALL | re.MULTILINE)
    if not match:
        st.error("❌ Không tìm thấy YAML front matter.")
        return {}

    try:
        data = yaml.safe_load(match.group(1))
        return data or {}
    except yaml.YAMLError as e:
        st.error(f"⚠️ Lỗi khi phân tích YAML: {e}")
        return {}

def get_file_content(file_id):
    """Đọc nội dung file từ Google Drive (dạng văn bản)."""
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    return fh.getvalue().decode("utf-8")

def extract_folder_id_from_url(url: str) -> str:
    """Trích xuất folder ID từ URL Google Drive."""
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None
    return match.group(1)

def select_working_folder():
    """Hiển thị ô nhập URL thư mục ở sidebar và trả về folder ID."""
    with st.sidebar:
        url = st.text_input("🔗 Nhập link thư mục Google Drive (Working Folder)")

    folder_id = extract_folder_id_from_url(url) if url else None

    if url and not folder_id:
        st.sidebar.warning("❌ Link không hợp lệ. Link phải có dạng chứa /folders/<ID>")

    return folder_id

def list_folder_contents(folder_id):
    """
    Liệt kê tất cả file và thư mục con trong một thư mục Google Drive.
    Trả về danh sách dict: {"name": ..., "id": ..., "mimeType": ...}
    """
    query = f"'{folder_id}' in parents and trashed = false"
    fields = "files(id, name, mimeType)"
    
    results = drive_service.files().list(q=query, fields=fields).execute()
    files = results.get("files", [])
    #files là 1 list với mỗi phần tử là 3 dict chứa id, name và kiểu dữ liệu
    return files

drive_service = get_drive_service()