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

# ------------------ 页面配置 & 现代 CSS 注入 ------------------
st.set_page_config(
    page_title="VocabMaster | 智能词书工坊", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定义 CSS 以提升质感
st.markdown("""
<style>
    /* 全局字体与背景优化 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 标题样式 */
    h1 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: -0.5px;
    }
    h2, h3 {
        color: #334155;
    }

    /* 按钮样式重构 - 更有触感 */
    div.stButton > button {
        border-radius: 12px;
        height: 3em;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    /* 主按钮特殊样式 */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
    }

    /* 卡片容器样式 */
    [data-testid="stExpander"] {
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        background-color: white;
        border-radius: 10px;
    }
    
    /* Metric 指标卡片 */
    [data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
    }
    
    /* 侧边栏微调 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #f1f5f9;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ 缓存资源加载 (保持不变) ------------------
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

# ------------------ 核心逻辑函数 (保持不变) ------------------
def save_to_github_library(filename, content, title, desc):
    """上传到 GitHub"""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("🔒 未配置 GitHub Token，无法连接云端数据库。")
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
            
        st.toast("✅ 发布成功！已同步至全球公共库", icon="🌍")
        time.sleep(1)
        st.rerun() # 刷新页面
        
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

# ------------------ 现代 UI 架构 ------------------

# 侧边栏：极简风格
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=60)
    st.title("VocabMaster")
    st.caption("AI 驱动的词汇构建工具")
    st.markdown("---")
    
    menu = st.radio(
        "导航", 
        ["⚡ 智能提取 (Extract)", "🌍 探索词库 (Explore)"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("""
    <div style='background: #e0e7ff; padding: 10px; border-radius: 8px; color: #3730a3; font-size: 0.85em;'>
    <b>💡 Pro Tip:</b><br>使用 Spacy 引擎可以获得更准确的词形还原效果。
    </div>
    """, unsafe_allow_html=True)

# === 页面 1: 制作生词本 ===
if "提取" in menu:
    st.title("⚡ 智能生词提取")
    st.markdown("上传字幕或文档，AI 自动清洗、还原并生成高频生词表。")
    
    # 状态初始化
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    
    # --- 步骤 1: 配置与上传 (卡片式布局) ---
    with st.container():
        c1, c2 = st.columns([1.5, 3], gap="large")
        
        with c1:
            st.subheader("1️⃣ 参数配置")
            with st.expander("🛠️ 高级设置", expanded=True):
                nlp_mode = st.selectbox("AI 引擎", ["nltk (极速版)", "spacy (精准版)"])
                mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
                min_len = st.slider("最短词长", 2, 8, 3)
                sort_order = st.selectbox("排序逻辑", ["按文本出现顺序", "A-Z 排序", "随机乱序"])
                
            st.markdown("🚫 **熟词过滤**")
            filter_file = st.file_uploader("上传熟词表 (.txt)", type=['txt'], label_visibility="collapsed")
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.success(f"已激活 {len(filter_set)} 个熟词过滤")

        with c2:
            st.subheader("2️⃣ 文件投喂")
            upload_zone = st.container(border=True)
            with upload_zone:
                uploaded_files = st.file_uploader(
                    "支持 .srt, .ass, .docx, .txt (支持批量)", 
                    type=['txt','srt','ass','vtt','docx'], 
                    accept_multiple_files=True
                )
                
                if uploaded_files:
                    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                    if st.button("🚀 开始 AI 分析", type="primary", use_container_width=True):
                        # 处理逻辑
                        all_raw_text = []
                        progress_bar = st.progress(0)
                        
                        for idx, file in enumerate(uploaded_files):
                            text = extract_text_from_bytes(file, file.name)
                            all_raw_text.append(text)
                            progress_bar.progress((idx + 1) / len(uploaded_files))
                        
                        full_text = "\n".join(all_raw_text)
                        
                        if full_text.strip():
                            with st.spinner(f"正在使用 {mode_key.upper()} 引擎深度清洗中..."):
                                words = process_words(full_text, mode_key, min_len, filter_set)
                                if sort_order == "A-Z 排序": words.sort()
                                elif sort_order == "随机乱序": random.shuffle(words)
                                st.session_state.result_words = words
                                st.toast(f"处理完成！提取了 {len(words)} 个生词", icon="✅")
                        else:
                            st.error("未能识别有效文本，请检查文件编码。")

    # --- 步骤 2: 结果仪表盘 (仅在有结果时显示) ---
    if st.session_state.result_words:
        st.markdown("---")
        st.subheader("3️⃣ 分析报告 & 导出")
        
        words = st.session_state.result_words
        
        # 仪表盘指标
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📚 生词总量", f"{len(words)}")
        m2.metric("📄 来源文件", f"{len(uploaded_files)}")
        m3.metric("⏱️ 预估学习时长", f"{math.ceil(len(words)/30)} min")
        m4.metric("🛡️ 过滤效率", "High" if filter_set else "Normal")
        
        # 内容展示区
        row_content = st.columns([2, 1])
        
        with row_content[0]:
            st.markdown("##### 📋 单词预览")
            # 使用 dataframe 展示更美观
            st.dataframe(
                [{"No.": i+1, "Word": w} for i, w in enumerate(words)],
                use_container_width=True,
                height=350,
                hide_index=True
            )
            
        with row_content[1]:
            st.markdown("##### 💾 动作面板")
            
            # 选项卡切换操作
            tab_local, tab_cloud = st.tabs(["📥 本地下载", "☁️ 云端发布"])
            
            with tab_local:
                st.info("生成 ZIP 包下载到本地设备。")
                chunk_size = st.number_input("文件切分 (词/文件)", value=5000, step=1000)
                
                zip_buffer = io.BytesIO()
                num_files = math.ceil(len(words) / chunk_size)
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i in range(num_files):
                        s = i * chunk_size
                        e = min(s + chunk_size, len(words))
                        zf.writestr(f"word_list_{i+1}.txt", "\n".join(words[s:e]))
                
                st.download_button(
                    "📦 立即下载", 
                    zip_buffer.getvalue(), 
                    "vocab_pack.zip", 
                    "application/zip", 
                    type="primary",
                    use_container_width=True
                )
                
            with tab_cloud:
                st.success("分享到公共库，帮助更多人。")
                with st.form("pub_form"):
                    s_name = st.text_input("文件名", value=f"vocab_{int(time.time())}.txt")
                    s_title = st.text_input("标题", placeholder="例如：老友记第一季高频词")
                    s_desc = st.text_area("描述", placeholder="简要介绍词书来源...")
                    if st.form_submit_button("🌍 发布", use_container_width=True):
                        if not s_name.endswith(".txt"):
                            st.warning("文件名需以 .txt 结尾")
                        else:
                            save_to_github_library(s_name, "\n".join(words), s_title, s_desc)

# === 页面 2: 公共词书库 ===
elif "探索" in menu:
    st.title("🌍 社区公共词书库")
    
    # 搜索栏
    col_search, _ = st.columns([2, 1])
    with col_search:
        search_query = st.text_input("🔍 搜索词书...", placeholder="输入标题或关键词").lower()

    # 读取数据
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    if not os.path.exists(LIBRARY_DIR): os.makedirs(LIBRARY_DIR)
    
    book_info = {}
    info_path = os.path.join(LIBRARY_DIR, INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f: book_info = json.load(f)
        except: pass

    try:
        files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    except: files = []
    
    # 过滤与排序
    filtered_files = []
    for f in files:
        meta = book_info.get(f, {})
        title = meta.get("title", f).lower()
        if search_query in title or search_query in f.lower():
            filtered_files.append(f)

    if not filtered_files:
        st.container().warning("📭 暂无匹配的词书，去上传第一个吧！")
    else:
        # 网格布局展示
        cols = st.columns(3)
        for i, filename in enumerate(filtered_files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f: file_content = f.read()
                word_count = len(file_content.splitlines())
                
                meta = book_info.get(filename, {})
                display_title = meta.get("title", filename)
                display_desc = meta.get("desc", "暂无描述")
                pub_date = meta.get("date", "Unknown")
                
                # 随机生成封面色条颜色
                colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEEAD"]
                card_color = colors[i % len(colors)]
                
                with cols[i % 3]:
                    # 卡片容器
                    with st.container(border=True):
                        # 装饰色条
                        st.markdown(f"<div style='height:8px; background-color:{card_color}; border-radius: 4px 4px 0 0; margin-bottom: 10px;'></div>", unsafe_allow_html=True)
                        
                        st.subheader(display_title)
                        st.caption(f"📅 {pub_date} | 📚 {word_count} 词")
                        
                        # 描述区域定高，防止参差不齐
                        st.markdown(
                            f"<div style='height: 60px; overflow: hidden; color: #666; font-size: 0.9em; margin-bottom: 10px;'>{display_desc}</div>", 
                            unsafe_allow_html=True
                        )
                        
                        st.download_button(
                            f"⬇️ 下载", 
                            file_content, 
                            filename, 
                            "text/plain",
                            key=f"dl_{i}",
                            use_container_width=True
                        )
            except Exception:
                continue
