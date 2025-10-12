#fandom_extractor.py

import streamlit as st
import requests
from bs4 import BeautifulSoup, NavigableString
from googlesearch import search
import html2text
from drive_module.drive_ops import get_file_content, get_file_id_from_link  # Import đúng từ package của bạn
from drive_module.auth import load_secret_value


def reset_manual_link():
    st.session_state["manual_link_input"] = ""

    
def format_output(name, image, nickname, sections, series, info_dump, template_file_id):
    template = get_file_content(template_file_id)

    format_dict = {
        "series": series,
        "name": name,
        "image": image,
        "info_dump": info_dump,
        "nickname": "\n".join([f"  - _{n}_" for n in nickname]) if nickname else "  - ",
    }

    for key in ["Personality", "Appearance", "Background"]:
        format_dict[key] = sections.get(key, "")

    return template.format(**format_dict)

def bulletize_infobox_lines(md_text):
    lines = md_text.strip().splitlines()
    bulletized = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in {'#', '-', '>', '*', ''}:
            bulletized.append(stripped)
        else:
            bulletized.append(f"- {stripped}")
    return "\n".join(bulletized)

def clean_html_element(tag):
    for sup in tag.find_all("sup"):
        sup.decompose()

    for a in tag.find_all("a"):
        href = a.get("href", "")
        classes = a.get("class", [])
        if "cite_note" in href or "reference" in classes:
            a.decompose()
        else:
            a.replace_with(a.get_text())

    spans_to_remove = []
    for span in tag.find_all("span"):
        if span is None:
            continue
        span_class = span.get("class", [])
        style = span.get("style", "")
        if (
            any("reference" in c for c in span_class)
            or "noprint" in span_class
            or "plainlinksneverexpand" in span_class
            or ("float:left" in style if style else False)
        ):
            spans_to_remove.append(span)

    for span in spans_to_remove:
        span.decompose()

    return tag

def get_first_fandom_link(query):
    search_query = f"{query} site:fandom.com"
    results = list(search(search_query, num_results=1))
    return results[0] if results else None

def get_clean_paragraph_text(p_tag):
    for tag in p_tag.find_all(['sup', 'span', 'img', 'figure']):
        tag.decompose()

    texts = []
    for elem in p_tag.descendants:
        if isinstance(elem, NavigableString):
            texts.append(str(elem))
        elif elem.name == "br":
            texts.append("\n")
    final = "".join(texts)
    return ' '.join(final.split())

def extract_sections(soup, sections=("Personality", "Appearance", "Background")):
    results = {}
    for sec in sections:
        header_tag = soup.find("span", {"id": sec}, class_="mw-headline")
        content = []

        if header_tag:
            parent = header_tag.parent  # thường là h2/h3...
            current = parent.find_next_sibling()
            to_extract = [parent]  # bao gồm cả tiêu đề

            while current:
                # Dừng khi gặp header mới
                if current.name and current.name.startswith("h"):
                    break
                to_extract.append(current)
                # Lưu nội dung nếu là đoạn văn
                if current.name == "p":
                    clean_text = get_clean_paragraph_text(current)
                    if clean_text:
                        content.append(clean_text)
                current = current.find_next_sibling()

            # Extract toàn bộ block (header + nội dung)
            for tag in to_extract:
                tag.extract()

        results[sec] = "\n\n".join(content) if content else ""

    return results


def extract_epithet_and_info(soup):
    nickname = []
    for div in soup.find_all("div", class_="pi-item", attrs={"data-source": True}):
        data_source = div.get("data-source", "").lower()
        if data_source in ["epithet", "nick_name"]:
            value_tag = div.find("div", class_="pi-data-value")
            if value_tag:
                values = [s.strip() for s in value_tag.stripped_strings if s.strip()]
                nickname.extend(values)
            div.extract()  # 🔥 Xóa cả block sau khi xử lý
    return nickname

def extract_metadata(soup):
    title_tag = soup.find("meta", property="og:title")
    image_tag = soup.find("meta", property="og:image")
    
    name = title_tag["content"] if title_tag else "Unknown"
    image = image_tag["content"] if image_tag else "Unknown"

    # 🔥 Xóa meta tags khỏi DOM sau khi lấy
    if title_tag:
        title_tag.extract()
    if image_tag:
        image_tag.extract()

    return name, image


def extract_wiki_name(title_tag):
    parts = title_tag.split(" | ")
    if len(parts) >= 2:
        return parts[1].replace(" Wiki", "").strip()
    return "output"

def info_dumping(soup):
    content_div = soup.find("div", id="mw-content-text")
    infobox = content_div.find("aside", class_="portable-infobox") if content_div else None

    markdown_infobox = ""
    markdown_content = ""

    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = False
    converter.body_width = 0

    if infobox:
        infobox.extract()
        cleaned_infobox = clean_html_element(infobox)
        markdown_infobox = converter.handle(str(cleaned_infobox))
        markdown_infobox = bulletize_infobox_lines(markdown_infobox)

    if content_div:
        cleaned_content = clean_html_element(content_div)
        markdown_content = converter.handle(str(cleaned_content))

    final_markdown = ""

    if markdown_infobox.strip():
        final_markdown += "# Infobox\n\n"
        final_markdown += markdown_infobox.strip() + "\n\n"

    if markdown_content.strip():
        final_markdown += "# Content\n\n"
        final_markdown += markdown_content.strip() + "\n"

    return final_markdown


# --- Streamlit UI ---
st.title("🧠 Fandom Character Extractor")
link = None
template_custome = st.sidebar.text_input("Nhập link template")
if template_custome: 
    template_file = get_file_id_from_link(template_custome)
else: 
    template_file = load_secret_value("app_config","fandom_template")

query = st.text_input("🔍 Nhập tên nhân vật:")
manual_link = st.sidebar.text_input("🔗 Nhập link trực tiếp (nếu có):", key="manual_link_input")

link = None
filename = st.text_input("Nhập tên file (không cần .md):", value="")
if manual_link:
    link = manual_link  # Ưu tiên link nhập tay
elif query:
    with st.spinner("Đang tìm kiếm..."):
        link = get_first_fandom_link(query)
    if not link:
        st.error("Không tìm thấy liên kết Fandom phù hợp.")
if link and filename:
    st.success(f"🔗 Đã tìm thấy: {link}")
    with st.spinner("Đang trích xuất nội dung..."):
        response = requests.get(link, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            st.error("❌ Không thể truy cập trang.")
        else:
            soup = BeautifulSoup(response.text, "html.parser")
            name, image = extract_metadata(soup)
            nickname = extract_epithet_and_info(soup)
            sections = extract_sections(soup)
            title_tag = soup.find("title")
            info_dump = info_dumping(soup)
            if title_tag:
                wiki_name = extract_wiki_name(title_tag.text.strip())
            result = format_output(name, image, nickname, sections, wiki_name, info_dump, template_file)
            st.code(result, language="markdown")
            st.download_button(
                label="Tải file Markdown",
                data=result.encode('utf-8'),
                file_name=f"{filename}.md",
                mime="text/markdown",
                on_click=reset_manual_link
            )
