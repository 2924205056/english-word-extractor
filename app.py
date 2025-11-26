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
import pandas as pd
import streamlit.components.v1 as components
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

# ------------------ 1. 页面配置 & CSS ------------------
st.set_page_config(
    page_title="VocabMaster | 智能词书工坊", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #fcfdfe; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .step-header { font-size: 1.1rem; font-weight: 700; color: #4f46e5; margin-bottom: 10px; display: flex; align-items: center; }
    [data-testid="stExpander"], [data-testid="stForm"] { background: white; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; }
    div.stButton > button { border-radius: 8px; padding: 0.5rem 1rem; font-weight: 600; transition: all 0.2s; }
    div.stButton > button:hover { transform: translateY(-1px); }
    .info-box { background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 15px; border-radius: 4px; color: #1e3a8a; font-size: 0.9em; margin-bottom: 15px; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    
    /* 代码块样式优化 */
    .stCodeBlock {
        max-height: 200px !important;
        overflow-y: auto !important;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background-color: #f8fafc;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ 2. 自定义复制按钮组件 ------------------
def render_copy_button(text_content, unique_key):
    safe_text = json.dumps(text_content)
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        .copy-btn {{
            width: 100%;
            padding: 10px;
            background-color: #4f46e5;
            color: white;
            border: none;
            border-radius: 6px;
            font-family: 'Segoe UI', sans-serif;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 4px rgba(79, 70, 229, 0.2);
        }}
        .copy-btn:hover {{
            background-color: #4338ca;
            transform: translateY(-1px);
            box-shadow: 0 4px 6px rgba(79, 70, 229, 0.3);
        }}
        .icon {{ margin-right: 6px; }}
    </style>
    </head>
    <body>
        <button id="btn_{unique_key}" class="copy-btn" onclick="copyText()">
            <span class="icon">📋</span> 一键复制 (Copy All)
        </button>
        <script>
        function copyText() {{
            const text = {safe_text};
            const textArea = document.createElement("textarea");
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {{
                document.execCommand('copy');
                const btn = document.getElementById("btn_{unique_key}");
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<span class="icon">✅</span> 成功！(Copied)';
                btn.style.backgroundColor = "#10b981";
                setTimeout(() => {{
                    btn.innerHTML = originalHTML;
                    btn.style.backgroundColor = "#4f46e5";
                }}, 2000);
            }} catch (err) {{}}
            document.body.removeChild(textArea);
        }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=45)

# ------------------ 3. 资源加载 ------------------
@st.cache_resource
def download_nltk_resources():
    resources = ["punkt", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "wordnet", "omw-1.4", "stopwords"]
    for r in resources:
        try: nltk.data.find(f'tokenizers/{r}')
        except LookupError: nltk.download(r, quiet=True)
        except ValueError: nltk.download(r, quiet=True)

@st.cache_resource
def load_spacy_model():
    if _HAS_SPACY:
        try: return spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception: return None
    return None

download_nltk_resources()
nlp_spacy = load_spacy_model()

# ------------------ 4. 核心逻辑 ------------------
def save_to_github_library(filename, content, title, desc):
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("🔒 系统未配置 GitHub Token。")
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
            
        local_lib = "library"
        if not os.path.exists(local_lib): os.makedirs(local_lib)
        with open(os.path.join(local_lib, filename), "w", encoding="utf-8") as f:
            f.write(content)
        
        local_info_path = os.path.join(local_lib, "info.json")
        local_info = {}
        if os.path.exists(local_info_path):
            with open(local_info_path, "r", encoding="utf-8") as f:
                try: local_info = json.load(f)
                except: pass
        local_info[filename] = info_data[filename]
        with open(local_info_path, "w", encoding="utf-8") as f:
            json.dump(local_info, f, indent=2, ensure_ascii=False)

        st.toast("✅ 发布成功！", icon="🎉")
        time.sleep(1.5)
        st.rerun()
        
    except Exception as e:
        st.error(f"上传失败: {e}")

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

# ------------------ 5. UI 架构 ------------------

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=50)
    st.markdown("### VocabMaster")
    st.caption("v9.0 Final Optimized")
    st.markdown("---")
    menu = st.radio("选择功能", ["⚡ 制作生词本", "🌍 公共词书库"])
    st.markdown("---")
    st.info("**小贴士**\n使用 Spacy 引擎还原词形更准。")

# === 制作生词本 ===
if menu == "⚡ 制作生词本":
    st.title("⚡ 智能生词提取工坊")
    
    # 资源导航
    with st.expander("📖 新手指南 & 资源推荐 (点击展开)", expanded=False):
        t1, t2, t3, t4 = st.tabs(["💡 操作", "🎬 影视", "📚 阅读", "🎧 听力"])
        with t1: st.markdown("1. 设置规则 -> 2. 上传文件 -> 3. 一键复制导入扇贝")
        with t2:
            c1, c2 = st.columns(2)
            c1.markdown("🎯 **[伪射手网 Assrt](https://assrt.net/)**\n<small>老牌字幕站，中英双语资源丰富。</small>", unsafe_allow_html=True)
            c1.markdown("📺 **[字幕库 Zimuku](http://zimuku.org/)**\n<small>美剧日剧更新快。</small>", unsafe_allow_html=True)
            c2.markdown("💎 **[SubHD](https://subhd.tv/)**\n<small>高清影视字幕首选。</small>", unsafe_allow_html=True)
            c2.markdown("🌎 **[OpenSubtitles](https://www.opensubtitles.org/)**\n<small>全球最大英文字幕库。</small>", unsafe_allow_html=True)
        with t3:
            st.markdown("🏛️ **[Project Gutenberg](https://www.gutenberg.org/)** (7万+公版电子书)")
        with t4:
            st.markdown("🔴 **[TED Talks](https://www.ted.com/)** (含 Transcript 演讲稿)")

    if 'result_words' not in st.session_state: st.session_state.result_words = []
    if 'source_files_count' not in st.session_state: st.session_state.source_files_count = 0
    
    # 操作区
    c_config, c_upload = st.columns([1, 2], gap="large")
    
    with c_config:
        st.markdown('<div class="step-header">1️⃣ 设置提取规则</div>', unsafe_allow_html=True)
        with st.container(border=True):
            nlp_mode = st.selectbox("AI 引擎", ["nltk (快速)", "spacy (精准)"])
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            
            min_len = st.number_input("单词最短长度", 3, 20, 3)
            
            # --- 新增：排序与切分 ---
            st.markdown("---")
            sort_order = st.selectbox("🔀 单词排序", ["按文本出现顺序", "A-Z 排序", "随机打乱"])
            chunk_size = st.number_input("📥 文件拆分大小 (词/文件)", 5000, 50000, 5000, step=1000)
            
            st.markdown("---")
            filter_file = st.file_uploader("屏蔽熟词表 (.txt)", type=['txt'])
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.caption(f"✅ 已加载 {len(filter_set)} 词")

    with c_upload:
        st.markdown('<div class="step-header">2️⃣ 上传与分析</div>', unsafe_allow_html=True)
        with st.container(border=True):
            uploaded_files = st.file_uploader("支持 .srt, .docx, .txt", type=['txt','srt','ass','docx'], accept_multiple_files=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if uploaded_files and st.button("🚀 开始提取", type="primary", use_container_width=True):
                my_bar = st.progress(0, text="读取文件...")
                all_text = []
                for i, f in enumerate(uploaded_files):
                    all_text.append(extract_text_from_bytes(f, f.name))
                    my_bar.progress((i+1)/len(uploaded_files))
                
                full_text = "\n".join(all_text)
                if full_text.strip():
                    my_bar.progress(100, text="AI 分析中...")
                    words = process_words(full_text, mode_key, min_len, filter_set)
                    
                    # 应用排序
                    if sort_order == "A-Z 排序": words.sort()
                    elif sort_order == "随机打乱": random.shuffle(words)
                    
                    st.session_state.result_words = words
                    st.session_state.source_files_count = len(uploaded_files)
                    my_bar.empty()
                    st.rerun()
                else:
                    st.error("未提取到文本。")

    # 结果区
    if st.session_state.result_words:
        st.divider()
        st.markdown('<div class="step-header">3️⃣ 结果与导出</div>', unsafe_allow_html=True)
        words = st.session_state.result_words
        content_str = "\n".join(words)
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            c1.metric("单词数", len(words))
            c2.metric("排序", sort_order)
            c3.metric("来源", f"{st.session_state.source_files_count} 文件")
            
        col_copy, col_act = st.columns([2, 1], gap="large")
        
        with col_copy:
            st.markdown("##### 📋 单词列表 (一键复制)")
            render_copy_button(content_str, "res_copy")
            st.code(content_str, language="text") # 备用展示
            
        with col_act:
            st.markdown("##### 🚀 操作")
            st.link_button("🦁 导入扇贝 (Web)", "https://web.shanbay.com/wordsweb/#/books", type="primary", use_container_width=True)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            
            # ZIP 下载
            zip_buffer = io.BytesIO()
            num_files = math.ceil(len(words) / chunk_size)
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(num_files):
                    s = i * chunk_size
                    e = min(s + chunk_size, len(words))
                    zf.writestr(f"word_list_{i+1}.txt", "\n".join(words[s:e]))
            st.download_button(f"📦 下载 ZIP ({num_files}个)", zip_buffer.getvalue(), "vocab.zip", "application/zip", use_container_width=True)
            
            st.markdown("---")
            with st.expander("☁️ 发布"):
                with st.form("pub"):
                    name = st.text_input("文件名(.txt)", value=f"v_{int(time.time())}.txt")
                    title = st.text_input("标题")
                    desc = st.text_area("简介")
                    if st.form_submit_button("提交"):
                        if name.endswith(".txt"): save_to_github_library(name, content_str, title, desc)

# === 公共词书库 ===
elif menu == "🌍 公共词书库":
    st.title("🌍 社区公共词书库")
    st.markdown("<div class='info-box'>汇集精选词书。点击下方<b>“展开”</b>按钮查看详情并复制。</div>", unsafe_allow_html=True)
    
    search_q = st.text_input("🔍 搜索...", "").lower()
    
    LIBRARY_DIR = "library"
    if not os.path.exists(LIBRARY_DIR): os.makedirs(LIBRARY_DIR)
    
    try:
        with open(os.path.join(LIBRARY_DIR, "info.json"), "r", encoding="utf-8") as f: book_info = json.load(f)
    except: book_info = {}
    
    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    visible = [f for f in files if search_q in f.lower() or search_q in book_info.get(f, {}).get("title", "").lower()]
    
    if not visible:
        st.warning("📭 暂无数据")
    else:
        cols = st.columns(3)
        for i, f in enumerate(visible):
            path = os.path.join(LIBRARY_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as file: content = file.read()
                count = len(content.splitlines())
                meta = book_info.get(f, {})
                title = meta.get("title", f)
                desc = meta.get("desc", "暂无描述")
                
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(f"📄 {title}")
                        st.caption(f"📝 {count} 词")
                        
                        # 操作按钮区
                        c1, c2 = st.columns(2)
                        with c1: st.link_button("🚀 导入", "https://web.shanbay.com/wordsweb/#/books", use_container_width=True)
                        with c2: st.download_button("⬇️ 下载", content, f, "text/plain", use_container_width=True)
                        
                        # 核心修改：默认折叠，保持清爽
                        with st.expander("👀 展开查看与复制"):
                            st.caption(desc)
                            render_copy_button(content, f"lib_copy_{i}")
                            st.code(content, language="text")
            except: continue
