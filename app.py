import streamlit as st
import io
import re
import zipfile
import math
import chardet
import os
import json
import random
import time
from github import Github

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

# ------------------ 页面配置 & 样式优化 ------------------
st.set_page_config(
    page_title="VocabMaster | 智能词书工坊", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS：增加呼吸感，优化阅读体验
st.markdown("""
<style>
    /* 全局背景色微调 */
    .stApp { background-color: #fcfdfe; }
    
    /* 标题增强 */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    
    /* 步骤标题样式 */
    .step-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #4f46e5;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    
    /* 卡片容器优化 */
    [data-testid="stExpander"], [data-testid="stForm"] {
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #e5e7eb;
    }
    
    /* 按钮优化 */
    div.stButton > button {
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button:hover { transform: translateY(-1px); }
    
    /* 提示框样式 */
    .info-box {
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 10px 15px;
        border-radius: 4px;
        color: #1e3a8a;
        font-size: 0.9em;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ 资源加载 (核心功能不变) ------------------
@st.cache_resource
def download_nltk_resources():
    resources = ["punkt", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "wordnet", "omw-1.4", "stopwords"]
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
def save_to_github_library(filename, content, title, desc):
    """GitHub 上传逻辑"""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("🔒 系统未配置 GitHub Token，无法连接云端。请联系管理员。")
            return

        token = st.secrets["GITHUB_TOKEN"]
        username = st.secrets["GITHUB_USERNAME"]
        repo_name = st.secrets["GITHUB_REPO"]
        
        g = Github(token)
        repo = g.get_repo(f"{username}/{repo_name}")
        
        library_path = f"library/{filename}"
        info_path = "library/info.json"
        
        try:
            contents = repo.get_contents(library_path)
            repo.update_file(library_path, f"Update {filename}", content, contents.sha)
        except:
            repo.create_file(library_path, f"Create {filename}", content)

        try:
            info_contents = repo.get_contents(info_path)
            info_data = json.loads(info_contents.decoded_content.decode("utf-8"))
        except:
            info_data = {}
            info_contents = None

        info_data[filename] = {
            "title": title,
            "desc": desc,
            "date": time.strftime("%Y-%m-%d"),
            "author": "User" 
        }
        
        new_info_str = json.dumps(info_data, indent=2, ensure_ascii=False)
        if info_contents:
            repo.update_file(info_path, "Update info.json", new_info_str, info_contents.sha)
        else:
            repo.create_file(info_path, "Create info.json", new_info_str)
            
        st.toast("✅ 发布成功！", icon="🎉")
        time.sleep(1.5)
        st.rerun()
        
    except Exception as e:
        st.error(f"连接云端失败: {e}")

def extract_text_from_bytes(file_obj, filename):
    if '.' in filename: ext = filename.split('.')[-1].lower()
    else: ext = 'txt'
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
            return ""
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception: return ""
    
    if ext in ['srt', 'vtt', 'ass']:
        clean_text = re.sub(r"<.*?>", "", text)
        clean_text = re.sub(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", "", clean_text)
        return clean_text
    return text

def process_words(all_text, mode, min_len, filter_set=None):
    TOKEN_RE = re.compile(r"[A-Za-z-]+")
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in TOKEN_RE.findall(all_text) if w]
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
        for w, tag in pos_tag(cleaned):
            wn = {'J':wordnet.ADJ,'V':wordnet.VERB,'N':wordnet.NOUN,'R':wordnet.ADV}.get(tag[0], None)
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

# ------------------ UI 布局设计 ------------------

# 侧边栏
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=50)
    st.markdown("### VocabMaster")
    st.caption("v2.0 Enhanced Edition")
    st.markdown("---")
    
    menu = st.radio(
        "选择功能", 
        ["⚡ 制作生词本", "🌍 公共词书库"],
        captions=["从文件提取单词", "下载现成的词书"]
    )
    
    st.markdown("---")
    st.info("**小贴士**\n使用 Spacy 引擎可以获得更准确的词形还原（例如将 'running' 还原为 'run'）。")

# === 功能一: 制作生词本 ===
if menu == "⚡ 制作生词本":
    st.title("⚡ 智能生词提取工坊")
    
    # --- 指引区域 (可折叠，保持页面整洁) ---
    with st.expander("📖 新手指南：如何制作一本生词本？(点击展开)", expanded=False):
        st.markdown("""
        1.  **准备文件**：找到你想学习的字幕文件 (`.srt`) 或文章 (`.docx`, `.txt`)。
        2.  **设置规则**：在左侧设置过滤条件，比如过滤掉太短的单词，或上传“熟词表”过滤掉你已经认识的词。
        3.  **上传分析**：拖入文件，点击开始，系统会自动提取高频生词。
        4.  **导出分享**：将结果下载为 ZIP，或发布到公共库分享给他人。
        """)

    # 状态管理
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    
    # --- 主操作区：左右分栏 ---
    c_config, c_upload = st.columns([1, 2], gap="large")
    
    # 左栏：配置 (Step 1)
    with c_config:
        st.markdown('<div class="step-header">1️⃣ 设置提取规则</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**基础设置**")
            nlp_mode = st.selectbox(
                "AI 处理引擎", 
                ["nltk (快速)", "spacy (精准)"],
                help="NLTK 速度极快适合大文件；Spacy 语法分析更准，适合精准学习。"
            )
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            
            min_len = st.number_input(
                "最短单词长度", 
                value=3, min_value=1,
                help="自动过滤掉长度小于此值的单词（如 a, is, to 等）。"
            )
            
            st.divider()
            
            st.markdown("**熟词过滤 (可选)**")
            filter_file = st.file_uploader(
                "上传熟词表 (.txt)", 
                type=['txt'],
                help="上传一个包含你已认识单词的txt文件（一行一个），系统将自动跳过这些词。"
            )
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.caption(f"✅ 已加载 {len(filter_set)} 个熟词")

    # 右栏：上传 (Step 2)
    with c_upload:
        st.markdown('<div class="step-header">2️⃣ 上传文件并分析</div>', unsafe_allow_html=True)
        with st.container(border=True):
            # 引导文案
            st.markdown("""
            <div class="info-box">
                支持批量上传字幕 (.srt, .ass) 或文档 (.docx, .txt)。<br>
                系统会自动去除时间轴和格式标签。
            </div>
            """, unsafe_allow_html=True)
            
            uploaded_files = st.file_uploader(
                "拖拽文件到这里，或点击浏览", 
                type=['txt','srt','ass','vtt','docx'], 
                accept_multiple_files=True
            )
            
            # 操作按钮与空隙
