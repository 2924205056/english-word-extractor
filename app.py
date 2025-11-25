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
    
    /* 资源链接样式 */
    .resource-link {
        text-decoration: none;
        color: #0366d6;
        font-weight: 500;
    }
    .resource-link:hover {
        text-decoration: underline;
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
        # 尝试获取 Secrets，如果不存在则给出友好提示
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
        
        # 1. 上传/更新词书文件
        try:
            contents = repo.get_contents(library_path)
            repo.update_file(library_path, f"Update {filename}", content, contents.sha)
        except:
            repo.create_file(library_path, f"Create {filename}", content)

        # 2. 更新 info.json
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
            
        # 3. 同时保存到本地 library 文件夹，确保立即在“公共库”可见
        local_lib = "library"
        if not os.path.exists(local_lib): os.makedirs(local_lib)
        
        with open(os.path.join(local_lib, filename), "w", encoding="utf-8") as f:
            f.write(content)
        
        local_info_path = os.path.join(local_lib, "info.json")
        # 读取本地现有info
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

# ------------------ UI 布局设计 ------------------

# 侧边栏
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=50)
    st.markdown("### VocabMaster")
    st.caption("v2.2 Resource Edition")
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
    
    # --- 指引区域 & 资源推荐 (新增) ---
    with st.expander("📖 新手指南 & 字幕资源推荐 (点击展开)", expanded=False):
        
        tab_guide, tab_resources = st.tabs(["💡 如何使用", "🔗 没字幕？去哪找"])
        
        with tab_guide:
            st.markdown("""
            1.  **准备文件**：找到你想学习的字幕文件 (`.srt`, `.ass`) 或英文文档。
            2.  **设置规则**：在左侧设置过滤条件，建议上传“熟词表”以过滤掉简单词。
            3.  **上传分析**：拖入文件，系统自动提取高频生词。
            4.  **导出分享**：生成结果后，可下载 ZIP 或发布到公共库。
            """)
            
        with tab_resources:
            st.markdown("这里整理了常用的字幕下载站点，方便您寻找学习素材：")
            c_res1, c_res2 = st.columns(2)
            with c_res1:
                st.markdown("🎯 **[伪射手网 (Assrt)](https://assrt.net/)**")
                st.caption("老牌字幕站，资源极其丰富，支持中英双语。")
                
                st.markdown("📺 **[字幕库 (Zimuku)](http://zimuku.org/)**")
                st.caption("美剧、日剧更新速度快，搜索体验好。")
            with c_res2:
                st.markdown("💎 **[SubHD](https://subhd.tv/)**")
                st.caption("界面清爽，高清影视字幕的首选之地。")
                
                st.markdown("🌎 **[OpenSubtitles](https://www.opensubtitles.org/)**")
                st.caption("全球最大的字幕库，寻找纯英文字幕的最佳选择。")

    # 状态管理初始化
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    if 'source_files_count' not in st.session_state: st.session_state.source_files_count = 0
    
    # --- 主操作区 ---
    c_config, c_upload = st.columns([1, 2], gap="large")
    
    # 左栏：配置
    with c_config:
        st.markdown('<div class="step-header">1️⃣ 设置提取规则</div>', unsafe_allow_html=True)
        with st.container(border=True):
            nlp_mode = st.selectbox("AI 处理引擎", ["nltk (快速)", "spacy (精准)"])
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            
            min_len = st.number_input("单词最短长度", value=3, min_value=1)
            
            st.divider()
            st.markdown("**熟词过滤 (可选)**")
            filter_file = st.file_uploader("上传熟词表 (.txt)", type=['txt'], label_visibility="collapsed")
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.caption(f"✅ 已加载 {len(filter_set)} 个熟词")

    # 右栏：上传与执行
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
            
            # 按钮区
            if uploaded_files:
                if st.button("🚀 开始智能提取", type="primary", use_container_width=True):
                    # 进度条
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
                        
                        # 更新 Session State
                        st.session_state.result_words = words
                        st.session_state.source_files_count = len(uploaded_files)
                        
                        my_bar.empty()
                        st.success(f"提取完成！共发现 {len(words)} 个生词。")
                        time.sleep(0.5)
                        st.rerun() # 强制刷新显示结果
                    else:
                        st.error("无法从文件中识别文字，请检查文件格式。")

    # --- 结果展示区 (Step 3) ---
    if st.session_state.result_words:
        st.divider()
        st.markdown('<div class="step-header">3️⃣ 结果预览与导出</div>', unsafe_allow_html=True)
        
        words = st.session_state.result_words
        
        # 结果概览栏
        with st.container(border=True):
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("📚 提取生词总数", f"{len(words)}")
            col_stat2.metric("⏱️ 建议学习天数", f"{math.ceil(len(words)/20)} 天")
            col_stat3.metric("🔍 词汇来源", f"{st.session_state.source_files_count} 个文件")

        col_preview, col_action = st.columns([1.5, 1], gap="medium")

        # 左侧：列表预览
        with col_preview:
            st.subheader("📋 单词列表")
            st.dataframe(
                [{"序号": i+1, "单词": w} for i, w in enumerate(words)],
                use_container_width=True,
                height=400,
                hide_index=True
            )

        # 右侧：导出操作
        with col_action:
            st.subheader("💾 保存方式")
            tab1, tab2 = st.tabs(["📥 下载到本地", "☁️ 分享到云端"])
            
            with tab1:
                st.caption("将单词打包为 .zip 下载")
                chunk_size = st.number_input("拆分大小 (词/文件)", value=5000, step=1000)
                
                # 准备 Zip
                zip_buffer = io.BytesIO()
                num_files = math.ceil(len(words) / chunk_size)
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i in range(num_files):
                        s = i * chunk_size
                        e = min(s + chunk_size, len(words))
                        zf.writestr(f"word_list_{i+1}.txt", "\n".join(words[s:e]))
                
                st.download_button(
                    "📦 点击下载 ZIP", 
                    zip_buffer.getvalue(), 
                    "my_vocabulary.zip", 
                    "application/zip", 
                    type="primary",
                    use_container_width=True
                )

            with tab2:
                st.caption("发布到“公共词书库”，与他人分享")
                with st.form("pub_form"):
                    s_name = st.text_input("文件名 (英文, .txt)", value=f"vocab_{int(time.time())}.txt")
                    s_title = st.text_input("标题", placeholder="如：老友记第一季高频词")
                    s_desc = st.text_area("简介", placeholder="这本词书来自于...")
                    
                    if st.form_submit_button("🌍 确认发布", use_container_width=True):
                        if not s_name.endswith(".txt"):
                            st.warning("文件名必须以 .txt 结尾")
                        else:
                            with st.spinner("正在上传..."):
                                save_to_github_library(s_name, "\n".join(words), s_title, s_desc)

# === 功能二: 公共词书库 ===
elif menu == "🌍 公共词书库":
    st.title("🌍 社区公共词书库")
    
    st.markdown("""
    <div class="info-box">
    这里汇集了大家上传的精选词书。您可以自由浏览、下载学习。<br>
    想要分享您的词书？请前往“制作生词本”页面进行发布。
    </div>
    """, unsafe_allow_html=True)
    
    # 搜索与过滤
    col_search, _ = st.columns([2, 1])
    with col_search:
        search_q = st.text_input("🔍 搜索词书标题...", placeholder="输入关键词搜索...").lower()

    # 数据加载
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    
    # 确保文件夹存在
    if not os.path.exists(LIBRARY_DIR): 
        os.makedirs(LIBRARY_DIR)
    
    book_info = {}
    try:
        with open(os.path.join(LIBRARY_DIR, INFO_FILE), "r", encoding="utf-8") as f:
            book_info = json.load(f)
    except: pass

    try:
        files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    except: files = []
    
    # 过滤文件
    visible_files = []
    for f in files:
        meta = book_info.get(f, {})
        t = meta.get("title", f).lower()
        if search_q in t or search_q in f.lower():
            visible_files.append(f)

    if not visible_files:
        st.warning("📭 暂时没有找到相关词书。如果您是第一次运行，请尝试先在“制作生词本”中上传并发布一个文件。")
    else:
        st.divider()
        # 卡片网格显示
        cols = st.columns(3)
        for i, filename in enumerate(visible_files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                count = len(content.splitlines())
                meta = book_info.get(filename, {})
                
                title = meta.get("title", filename)
                desc = meta.get("desc", "暂无描述")
                date = meta.get("date", "")
                
                # 轮询列
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(f"📄 {title}")
                        st.caption(f"📅 {date} | 📝 {count} 词")
                        st.markdown(f"<div style='height:40px;overflow:hidden;color:grey;font-size:0.9em'>{desc}</div>", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.download_button(
                            "⬇️ 下载词表", 
                            content, 
                            filename, 
                            "text/plain",
                            key=f"btn_{i}",
                            use_container_width=True
                        )
            except: continue
