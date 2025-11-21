import streamlit as st
import io
import re
import zipfile
import math
import chardet
import os
import json  # 新增：用于读取描述文件

# NLP Imports
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet, stopwords
from nltk import pos_tag

# DOCX Import
from docx import Document

# Optional Spacy
try:
    import spacy
    _HAS_SPACY = True
except ImportError:
    _HAS_SPACY = False

# ------------------ 页面配置 ------------------
st.set_page_config(page_title="万能词书平台", page_icon="📘", layout="wide")

# ------------------ 缓存资源加载 ------------------
@st.cache_resource
def download_nltk_resources():
    """静默下载 NLTK 资源"""
    resources = [
        "punkt", 
        "averaged_perceptron_tagger", 
        "averaged_perceptron_tagger_eng", 
        "wordnet", 
        "omw-1.4", 
        "stopwords"
    ]
    for r in resources:
        try:
            nltk.data.find(f'tokenizers/{r}')
        except LookupError:
            nltk.download(r, quiet=True)
        except ValueError:
            nltk.download(r, quiet=True)

@st.cache_resource
def load_spacy_model():
    if _HAS_SPACY:
        try:
            return spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            return None
    return None

download_nltk_resources()
nlp_spacy = load_spacy_model()

# ------------------ 核心逻辑函数 ------------------

def extract_text_from_bytes(file_obj, filename):
    if '.' in filename:
        ext = filename.split('.')[-1].lower()
    else:
        ext = 'txt'
    text = ""
    try:
        if ext == 'docx':
            doc = Document(file_obj)
            text_content = []
            for p in doc.paragraphs:
                if p.text.strip(): text_content.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip(): text_content.append(cell.text)
            text = "\n".join(text_content)
        elif ext == 'doc':
            st.error("不支持 .doc，请转存为 .docx")
            return ""
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception as e:
        return ""
    
    # 简单清洗
    if ext in ['srt', 'vtt', 'ass']:
        clean_text = re.sub(r"<.*?>", "", text)
        return clean_text
    return text

def get_wordnet_pos(tag):
    if tag.startswith('J'): return wordnet.ADJ
    if tag.startswith('V'): return wordnet.VERB
    if tag.startswith('N'): return wordnet.NOUN
    if tag.startswith('R'): return wordnet.ADV
    return None

def process_words(all_text, mode, min_len, filter_set=None):
    TOKEN_RE = re.compile(r"[A-Za-z-]+")
    raw_tokens = TOKEN_RE.findall(all_text)
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in raw_tokens]
    cleaned = [w for w in cleaned if w]
    lemmatized = []
    
    if mode == "spacy" and nlp_spacy:
        chunk_size = 50000
        chunks = [cleaned[i:i + chunk_size] for i in range(0, len(cleaned), chunk_size)]
        for chunk in chunks:
            doc = nlp_spacy(" ".join(chunk))
            for token in doc:
                lw = token.lemma_.lower()
                if lw.isalpha() and wordnet.synsets(lw): lemmatized.append(lw)
    else:
        lemmatizer = WordNetLemmatizer()
        tagged = pos_tag(cleaned)
        for w, tag in tagged:
            wn = get_wordnet_pos(tag)
            lw = lemmatizer.lemmatize(w, wn) if wn else lemmatizer.lemmatize(w)
            if wordnet.synsets(lw): lemmatized.append(lw)

    seen = set()
    final_words = []
    sys_stopwords = set(stopwords.words('english'))
    for w in lemmatized:
        if len(w) < min_len: continue
        if w in sys_stopwords: continue
        if filter_set and w in filter_set: continue
        if w not in seen:
            seen.add(w)
            final_words.append(w)
    return final_words

# ------------------ 主界面导航 ------------------

st.sidebar.title("功能导航")
page = st.sidebar.radio("选择模式:", ["🛠️ 制作生词本", "📚 公共词书库"])

# ==================== 页面 1: 制作生词本 ====================
if page == "🛠️ 制作生词本":
    st.title("🛠️ 英语生词提取器")
    st.markdown("上传文档或字幕，一键提取生词。")

    with st.sidebar:
        st.divider()
        st.header("⚙️ 提取设置")
        nlp_mode = st.selectbox("引擎", ["nltk (快)", "spacy (准)"], index=0)
        mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
        min_len = st.number_input("最短词长", value=3)
        chunk_size = st.number_input("切分大小", value=5000)
        filter_file = st.file_uploader("过滤词表", type=['txt'])
        filter_set = set()
        if filter_file:
            c = filter_file.getvalue().decode("utf-8", errors='ignore')
            filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
            st.success(f"已加载 {len(filter_set)} 个过滤词")

    uploaded_files = st.file_uploader("上传文件", type=['txt','srt','ass','vtt','docx'], accept_multiple_files=True)

    if uploaded_files and st.button("🚀 开始提取", type="primary"):
        all_raw_text = []
        for file in uploaded_files:
            text = extract_text_from_bytes(file, file.name)
            all_raw_text.append(text)
        
        full_text = "\n".join(all_raw_text)
        if full_text.strip():
            with st.spinner("正在分析单词..."):
                result_words = process_words(full_text, mode_key, min_len, filter_set)
            
            st.success(f"提取成功！共 {len(result_words)} 个单词。")
            
            with st.expander("👀 预览结果"):
                st.write(", ".join(result_words[:100]))
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("word_list.txt", "\n".join(result_words))
            
            st.download_button("📥 下载结果 (TXT)", zip_buffer.getvalue(), "words.zip", "application/zip")
        else:
            st.warning("未提取到文本。")

# ==================== 页面 2: 公共词书库 (已更新支持描述) ====================
elif page == "📚 公共词书库":
    st.title("📚 公共词书库")
    st.markdown("这里存放了站长精选的生词本，大家可以免费下载。")
    
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json" # 描述文件的名字
    
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
        st.info(f"请在 GitHub 创建 '{LIBRARY_DIR}' 文件夹。")
    
    # 1. 尝试读取 info.json 里的描述信息
    book_info = {}
    info_path = os.path.join(LIBRARY_DIR, INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                book_info = json.load(f)
        except Exception as e:
            st.error(f"描述文件读取失败 (Json格式错误): {e}")

    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    
    if not files:
        st.warning("📭 书架目前是空的，请上传 .txt 文件到 GitHub 的 library 文件夹！")
    else:
        col1, col2 = st.columns(2)
        for i, filename in enumerate(files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            word_count = len(file_content.splitlines())
            
            # 获取该文件的描述信息 (如果没写，就用默认值)
            meta = book_info.get(filename, {})
            display_title = meta.get("title", filename) # 如果有标题就用标题，没有就用文件名
            display_desc = meta.get("desc", "暂无描述")   # 获取描述
            
            with (col1 if i % 2 == 0 else col2):
                with st.container(border=True):
                    # 显示带 emoji 的标题
                    st.subheader(f"📄 {display_title}")
                    
                    # 显示描述信息 (灰色小字)
                    if display_desc != "暂无描述":
                        st.info(display_desc)
                    else:
                        st.caption("无详细描述")
                        
                    st.caption(f"📚 单词数: **{word_count}**")
                    
                    st.download_button(
                        label=f"📥 下载 {filename}",
                        data=file_content,
                        file_name=filename,
                        mime="text/plain"
                    )
