#drive_ops.py

import streamlit as st
import re
from .auth import get_drive_service
from googleapiclient.http import MediaIoBaseDownload
import io
import yaml


def get_file_id_from_link(url):
    try:
        start = url.index("/d/") + 3
        end = url.index("/view", start)
        return url[start:end]
    except ValueError:
        return None

def get_images_in_folder(folder_id):
    """
    Trả về danh sách các file ảnh trong thư mục, mỗi phần tử là tuple (name, file_id).
    Các ảnh có MIME type bắt đầu bằng 'image/'.
    """
    all_files = list_folder_contents(folder_id)
    image_files = [
        (f["name"], f["id"])
        for f in all_files
        if f["mimeType"].startswith("image/")
    ]
    return image_files

def get_or_cache_data(key, loader_func, dependencies=None):
    dep_key = f"{key}__deps"
    if key in st.session_state and dep_key in st.session_state:
        if st.session_state[dep_key] == dependencies:
            return st.session_state[key]
    data = loader_func()
    st.session_state[key] = data
    st.session_state[dep_key] = dependencies
    return data


def extract_bullet_items_from_section(content, section_name):

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

def extract_yaml(content):

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

def deep_update(d, u):
    """Merge dict u vào dict d, giữ tất cả key, merge dict và list sâu"""
    for k, v in u.items():
        if k in d:
            if isinstance(d[k], dict) and isinstance(v, dict):
                deep_update(d[k], v)
            elif isinstance(d[k], list) and isinstance(v, list):
                d[k].extend(x for x in v if x not in d[k])  # append nhưng tránh trùng
            else:
                d[k] = v  # ghi đè nếu không cùng type
        else:
            d[k] = v
    return d


def extract_yamls(datas):
    """
    Trích xuất YAML từ nhiều file và merge lại thành một dict duy nhất.
    Nếu cùng key, dữ liệu sẽ được gộp vào thay vì ghi đè.
    """
    merged = {}
    for raw_data in datas:
        data = extract_yaml(raw_data)
        if data:
            deep_update(merged, data)
    return merged



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

def list_folder_contents(folder_id, parent = None):

    # Lấy danh sách file/folder con
    query = f"'{folder_id}' in parents and trashed = false"
    fields = "files(id, name, mimeType, parents, modifiedTime)"
    results = drive_service.files().list(q=query, fields=fields).execute()
    files = results.get("files", [])

    return files



def list_folder_contents_recursive(folder_id):

    # Lấy các item trực tiếp trong folder hiện tại
    items = list_folder_contents(folder_id, 1)

    all_items = []
    for item in items:
        all_items.append(item)  # luôn thêm chính item đó vào danh sách

        # Nếu item là folder => gọi đệ quy để lấy tiếp nội dung
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            sub_items = list_folder_contents_recursive(item["id"])
            all_items.extend(sub_items)

    return all_items

def build_tree(items):
    tree = {}

    # Khởi tạo tất cả folder
    for item in items:
        if item["mimeType"] == "application/vnd.google-apps.folder":
            tree[item["id"]] = {
                "name": item["name"],
                "files": [],
                "subfolders": []
            }
    root = set()
    # Gắn file và subfolder vào đúng folder cha
    for item in items:
        parents = item.get("parents", [])
        if not parents:
            continue
        parent_id = parents[0]
        if parent_id not in tree:
            root.add(parent_id)
            continue

        if item["mimeType"] == "application/vnd.google-apps.folder":
            tree[parent_id]["subfolders"].append(item["id"])
        elif item["mimeType"] == "text/markdown":
            tree[parent_id]["files"].append(item["id"] + "|" + item["modifiedTime"] + "|" + item["name"])
    root_id = list(root)[0]
    tree[root_id] = {
        "name": "ROOT",
        "files": [],
        "subfolders": list(tree.keys())
    }
    return tree




def collect(folder, tree, checkbox, memo=None, folder_all_files=None):
    if memo is None:
        memo = {}
        folder_all_files = {}
        
    contents = []
    all_files = []
    for file in tree[folder].get("files", []):
        if file.endswith(".md"):          # chỉ xử lý file kết thúc bằng .md
            fikle_attribute = file.split("|")
            file_content = get_or_cache_data(
                key=f"folder_contents_{file}",
                loader_func=lambda: get_file_content(fikle_attribute[0]),
                dependencies={"sorted_compo_id": fikle_attribute[1]}
            )
            all_files.append(file)
            contents.append(file_content)

    for sub in tree[folder]["subfolders"]:
        sub_contents, memo, fol, folder_all_files = collect(sub, tree, checkbox, memo, folder_all_files)
        contents.extend(sub_contents)
        all_files.extend(fol)

    memo[folder] = contents
    folder_all_files[folder] = all_files
    return contents, memo, all_files, folder_all_files

drive_service = get_drive_service()
