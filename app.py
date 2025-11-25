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
import streamlit.components.v1 as components # 引入组件库用于自定义按钮
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

# ------------------ 1. 页面配置 & 现代 CSS 注入 ------------------
st.set_page_config(
    page_title="VocabMaster | 智能词书工坊", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS
st.markdown("""
<style>
    .stApp { background-color: #fcfdfe; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .step-header { font-size: 1.1rem; font-weight: 700; color: #4f46e5; margin-bottom: 10px; display: flex; align-items: center; }
    [data-testid="stExpander"], [data-testid="stForm"] { background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; }
    div.stButton > button { border-radius: 8px; padding: 0.5rem 1rem; font-weight: 600; transition: all 0.2s; }
    div.stButton > button:hover { transform: translateY(-1px); }
    .info-box { background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 15px; border-radius: 4px; color: #1e3a8a; font-size: 0.9em; margin-bottom: 15px; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
    
    /* 代码块样式：作为备用展示，稍微淡化 */
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

# ------------------ 2. 工具函数：自定义复制按钮 ------------------
def render_copy_button(text_content, unique_key):
    """
    渲染一个醒目的自定义 HTML/JS 复制按钮
    """
    # 安全转义文本内容
    safe_text = json.dumps(text_content)
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        .copy-btn {{
            width: 100%;
            padding: 12px;
            background-color: #4f46e5; /* 醒目蓝紫色 */
            color: white;
            border: none;
            border-radius: 8px;
            font-family: 'Segoe UI', sans-serif;
            font-weight: 600;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 6px rgba(79, 70, 229, 0.2);
        }}
        .copy-btn:hover {{
            background-color: #4338ca;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(79, 70, 229, 0.3);
        }}
        .copy-btn:active {{
            transform: translateY(0);
        }}
        .icon {{ margin-right: 8px; font-size: 18px; }}
    </style>
    </head>
    <body>
        <button id="btn_{unique_key}" class="copy-btn" onclick="copyText()">
            <span class="icon">📋</span> 点击一键复制所有单词 (Copy All)
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
                const originalText = btn.innerHTML;
                
                // 成功反馈
                btn.innerHTML = '<span class="icon">✅</span> 复制成功！(Copied)';
                btn.style.backgroundColor = "#10b981"; // 绿色
                
                // 2秒后恢复
                setTimeout(() => {{
                    btn.innerHTML = originalText;
                    btn.style.backgroundColor = "#4f46e5"; // 恢复蓝紫色
                }}, 2000);
            }} catch (err) {{
                console.error('Fallback: Oops, unable to copy', err);
            }}
            document.body.removeChild(textArea);
        }}
        </script>
    </body>
    </html>
    """
    # 渲染 HTML 组件，设定固定高度
    components.html(html_code, height=60)


# ------------------ 3. 缓存资源加载 ------------------
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

# ------------------ 4. 核心逻辑函数 ------------------
def save_to_github_library(filename, content, title, desc):
    """GitHub 上传逻辑"""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("🔒 系统未配置 GitHub Token，无法连接云端。请在 .streamlit/secrets.toml 中配置。")
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

# ------------------ 5. UI 布局设计 ------------------

# === 侧边栏 ===
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=50)
    st.markdown("### VocabMaster")
    st.caption("v8.0 Pro Copy Edition")
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
    
    # --- 指引区域 ---
    with st.expander("📖 新手指南 & 宝藏资源导航 (点击展开)", expanded=False):
        tab_guide, tab_subs, tab_books, tab_learn = st.tabs(["💡 操作指引", "🎬 影视字幕", "📚 名著 & 阅读", "🎧 名师 & 听力"])
        
        with tab_guide:
            st.markdown("""
            <div style="padding: 10px; background: #f8f9fa; border-radius: 8px;">
            <h4 style="margin-top:0">🚀 快速上手流程</h4>
            <ol>
                <li><b>定规则</b>：设置提取规则，包括文件拆分大小。</li>
                <li><b>传文件</b>：将字幕或文档拖入上传区，点击提取。</li>
                <li><b>去背诵</b>：使用<b>醒目的蓝色按钮</b>一键复制，跳转扇贝网批量导入。</li>
            </ol>
            </div>
            """, unsafe_allow_html=True)
            
        with tab_subs:
            st.info("💡 提示：下载 .srt 或 .ass 格式的字幕文件，直接拖入本工具即可提取生词。")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("🎯 **[伪射手网 (Assrt)](https://assrt.net/)**")
                st.markdown("📺 **[字幕库 (Zimuku)](http://zimuku.org/)**")
            with c2:
                st.markdown("💎 **[SubHD](https://subhd.tv/)**")
                st.markdown("🌎 **[OpenSubtitles](https://www.opensubtitles.org/)**")

        with tab_books:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("🏛️ **[Project Gutenberg](https://www.gutenberg.org/)**")
                st.markdown("📖 **[Standard Ebooks](https://standardebooks.org/)**")
            with c2:
                st.markdown("📰 **[The Economist](https://www.economist.com/)**")
                st.markdown("🐲 **[China Daily](https://language.chinadaily.com.cn/)**")

        with tab_learn:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("🔴 **[TED Talks](https://www.ted.com/)**")
                st.markdown("🇬🇧 **[BBC Learning English](https://www.bbc.co.uk/learningenglish/)**")
            with c2:
                st.markdown("🎓 **[Coursera](https://www.coursera.org/)**")
                st.markdown("🇺🇸 **[NPR News](https://www.npr.org/)**")

    # 状态初始化
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    if 'source_files_count' not in st.session_state: st.session_state.source_files_count = 0
    
    # --- 主操作区 ---
    c_config, c_upload = st.columns([1, 2], gap="large")
    
    with c_config:
        st.markdown('<div class="step-header">1️⃣ 设置提取规则</div>', unsafe_allow_html=True)
        with st.container(border=True):
            nlp_mode = st.selectbox("AI 处理引擎", ["nltk (快速)", "spacy (精准)"])
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            
            min_len = st.number_input("单词最短长度", value=3, min_value=1)
            
            st.markdown("---")
            chunk_size = st.number_input(
                "📥 文件拆分大小 (词/文件)", 
                value=5000, 
                step=1000,
                help="当下载 ZIP 时，会将单词表切割成多个文件。"
            )
            
            st.markdown("---")
            filter_file = st.file_uploader("屏蔽词表 (.txt)", type=['txt'], label_visibility="visible")
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.caption(f"✅ 已加载 {len(filter_set)} 个熟词")

    with c_upload:
        st.markdown('<div class="step-header">2️⃣ 上传文件并分析</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div class='info-box'>支持 .srt, .ass, .docx, .txt 批量上传</div>", unsafe_allow_html=True)
            
            uploaded_files = st.file_uploader(
                "文件上传区", 
                type=['txt','srt','ass','vtt','docx'], 
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if uploaded_files:
                if st.button("🚀 开始智能提取", type="primary", use_container_width=True):
                    progress_text = "正在读取文件..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    all_raw_text = []
                    for idx, file in enumerate(uploaded_files):
                        text = extract_text_from_bytes(file, file.name)
                        all_raw_text.append(text)
                        my_bar.progress((idx + 1) / len(uploaded_files), text=f"解析文件: {file.name}")
                    
                    full_text = "\n".join(all_raw_text)
                    
                    if full_text.strip():
                        my_bar.progress(100, text=f"正在使用 {mode_key.upper()} 引擎清洗数据...")
                        words = process_words(full_text, mode_key, min_len, filter_set)
                        st.session_state.result_words = words
                        st.session_state.source_files_count = len(uploaded_files)
                        my_bar.empty()
                        st.success(f"提取完成！共发现 {len(words)} 个生词。")
                        time.sleep(0.5)
                        st.rerun() 
                    else:
                        st.error("无法从文件中识别文字，请检查文件格式。")

    # --- 结果展示区 ---
    if st.session_state.result_words:
        st.divider()
        st.markdown('<div class="step-header">3️⃣ 结果预览与导入</div>', unsafe_allow_html=True)
        
        words = st.session_state.result_words
        content_str = "\n".join(words)
        
        with st.container(border=True):
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("📚 提取生词总数", f"{len(words)}")
            col_stat2.metric("⏱️ 建议学习天数", f"{math.ceil(len(words)/20)} 天")
            col_stat3.metric("🔍 词汇来源", f"{st.session_state.source_files_count} 个文件")

        # 布局：左侧(复制区) + 右侧(操作按钮)
        col_copy, col_actions = st.columns([2, 1], gap="large")

        # 左侧：醒目复制区
        with col_copy:
            st.markdown("##### 📋 单词列表 (一键复制)")
            # 1. 渲染自定义的大按钮
            render_copy_button(content_str, "result_area")
            
            # 2. 备用展示区 (代码块)
            st.caption("👇 下方为文本预览 (Preview)")
            st.code(content_str, language="text")

        # 右侧：操作按钮群
        with col_actions:
            st.markdown("##### 🚀 快速操作")
            
            st.link_button(
                "🦁 导入扇贝网 (Web端)", 
                "https://web.shanbay.com/wordsweb/#/books", 
                help="点击跳转，登录后选择'上传词书'，粘贴左侧复制的单词。",
                type="primary", 
                use_container_width=True
            )
            
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            zip_buffer = io.BytesIO()
            num_files = math.ceil(len(words) / chunk_size)
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(num_files):
                    s = i * chunk_size
                    e = min(s + chunk_size, len(words))
                    zf.writestr(f"word_list_{i+1}.txt", "\n".join(words[s:e]))
            
            st.download_button(
                f"📦 下载 ZIP ({num_files}个文件)", 
                zip_buffer.getvalue(), 
                "my_vocabulary.zip", 
                "application/zip", 
                use_container_width=True
            )
            
            st.markdown("---")
            
            with st.expander("☁️ 发布到公共库", expanded=False):
                with st.form("pub_form"):
                    s_name = st.text_input("文件名 (英文)", value=f"vocab_{int(time.time())}.txt")
                    s_title = st.text_input("标题", placeholder="如：老友记第一季")
                    s_desc = st.text_area("简介")
                    if st.form_submit_button("发布"):
                        if not s_name.endswith(".txt"):
                            st.warning("需 .txt 结尾")
                        else:
                            save_to_github_library(s_name, content_str, s_title, s_desc)

# === 功能二: 公共词书库 ===
elif menu == "🌍 公共词书库":
    st.title("🌍 社区公共词书库")
    
    st.markdown("""
    <div class="info-box">
    汇集社区精选词书。<b>点击蓝色大按钮复制</b>，即可去扇贝网导入学习。
    </div>
    """, unsafe_allow_html=True)
    
    col_search, _ = st.columns([2, 1])
    with col_search:
        search_q = st.text_input("🔍 搜索词书...", placeholder="输入关键词...").lower()

    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    if not os.path.exists(LIBRARY_DIR): os.makedirs(LIBRARY_DIR)
    
    book_info = {}
    try:
        with open(os.path.join(LIBRARY_DIR, INFO_FILE), "r", encoding="utf-8") as f:
            book_info = json.load(f)
    except: pass

    try:
        files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    except: files = []
    
    visible_files = []
    for f in files:
        meta = book_info.get(f, {})
        t = meta.get("title", f).lower()
        if search_q in t or search_q in f.lower():
            visible_files.append(f)

    if not visible_files:
        st.warning("📭 暂无公共词书。")
    else:
        st.divider()
        cols = st.columns(3)
        for i, filename in enumerate(visible_files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                count = len(content.splitlines())
                meta = book_info.get(filename, {})
                title = meta.get("title", filename)
                desc = meta.get("desc", "暂无描述")
                
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(f"📄 {title}")
                        st.caption(f"📝 {count} 词")
                        
                        # 核心修改：使用醒目的大按钮代替简单的代码展示
                        render_copy_button(content, f"lib_{i}")
                        
                        # 代码块作为预览，高度受限
                        st.code(content, language="text")
                        
                        c_imp, c_dl = st.columns(2)
                        with c_imp:
                            st.link_button(
                                "🚀 导入扇贝", 
                                "https://web.shanbay.com/wordsweb/#/books", 
                                use_container_width=True
                            )
                        with c_dl:
                            st.download_button(
                                "⬇️ 下载", content, filename, "text/plain",
                                key=f"dl_{i}", use_container_width=True
                            )
            except: continue
