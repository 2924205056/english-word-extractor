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
import streamlit.components.v1 as components
from github import Github

# NLP Imports
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet, stopwords
from nltk import pos_tag
from docx import Document

# Optional Spacy
try:
    import spacy
    _HAS_SPACY = True
except ImportError:
    _HAS_SPACY = False

# ------------------ 0. 初始化 & 资源加载 ------------------
WORDLIST_DIR = "wordlists"
if not os.path.exists(WORDLIST_DIR):
    os.makedirs(WORDLIST_DIR)
    # 创建演示数据
    if not os.path.exists(os.path.join(WORDLIST_DIR, "primary.txt")):
        with open(os.path.join(WORDLIST_DIR, "primary.txt"), "w", encoding="utf-8") as f:
            f.write("a\nan\nthe\nis\nare\nam\nhello\ngood\nbook\npen")

PRESET_WORDLISTS = {
    "👶 小学核心词": os.path.join(WORDLIST_DIR, "primary.txt"),
    "👦 中考必备词": os.path.join(WORDLIST_DIR, "zhongkao.txt"),
    "👨‍🎓 高考3500词": os.path.join(WORDLIST_DIR, "gaokao.txt"),
}

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

# ------------------ 1. 页面配置 & CSS 设计系统 (Core UI) ------------------
st.set_page_config(
    page_title="VocabMaster", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入深度定制的 CSS，复刻 HTML 模板的 Tailwind 风格
st.markdown("""
<style>
    /* 引入字体：Plus Jakarta Sans & Noto Sans SC */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    /* ----- 全局重置 ----- */
    .stApp {
        background-color: #F8FAFC; /* Slate-50 */
        font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
        color: #1e293b;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #0f172a;
    }

    /* ----- 侧边栏美化 ----- */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #f1f5f9;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
    }
    /* 隐藏侧边栏默认的顶部 padding */
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }

    /* ----- 卡片 (Cards) ----- */
    /* 我们将使用 st.container(border=True) 但通过 CSS 覆盖它的样式 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border: 1px solid #e2e8f0; /* Slate-200 */
        border-radius: 16px;
        background-color: #ffffff;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05); /* Soft Shadow */
        padding: 24px;
    }

    /* ----- 按钮 (Buttons) ----- */
    /* Primary Button (Teal) */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%); /* Teal Gradient */
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 700;
        font-size: 0.95rem;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.2);
        transition: all 0.3s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(15, 118, 110, 0.3);
    }
    
    /* Secondary Button */
    div.stButton > button[kind="secondary"] {
        background-color: #F0FDFA; /* Teal-50 */
        color: #0F766E; /* Teal-700 */
        border: 1px solid #CCFBF1;
        border-radius: 10px;
        font-weight: 600;
    }

    /* ----- 输入组件 ----- */
    /* Selectbox, TextInput, NumberInput */
    .stSelectbox > div > div, .stTextInput > div > div, .stNumberInput > div > div {
        background-color: #F8FAFC;
        border: 1px solid #cbd5e1;
        border-radius: 10px;
        color: #334155;
    }
    .stSelectbox > div > div:focus-within {
        border-color: #2DD4BF;
        box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.1);
    }
    
    /* File Uploader - Dotted Style */
    [data-testid="stFileUploader"] {
        background-color: #F8FAFC;
        border: 2px dashed #cbd5e1;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        transition: border-color 0.3s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #2DD4BF;
        background-color: #F0FDFA;
    }

    /* ----- 3D 书籍特效 (移植自 HTML) ----- */
    .book-container {
        perspective: 1000px;
        margin-bottom: 20px;
    }
    .book-3d {
        width: 100%;
        aspect-ratio: 3/4;
        border-radius: 4px 12px 12px 4px;
        position: relative;
        transform-style: preserve-3d;
        transition: transform 0.3s ease;
        box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
        cursor: pointer;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        padding: 15px;
        overflow: hidden;
    }
    .book-3d:hover {
        transform: translateY(-8px) rotateY(-5deg) scale(1.02);
        box-shadow: 10px 15px 25px rgba(0,0,0,0.15);
    }
    /* 书脊效果 */
    .book-spine {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 12px;
        background: linear-gradient(90deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 100%);
        z-index: 10;
        border-right: 1px solid rgba(0,0,0,0.05);
    }
    .book-badge {
        position: absolute;
        top: 12px;
        left: 16px;
        background: rgba(255,255,255,0.9);
        backdrop-filter: blur(4px);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 800;
        color: #1e293b;
        z-index: 20;
    }

    /* 隐藏 Streamlit 自带的 Header 装饰条 */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .stMain {
        margin-top: -60px; /* 拉起内容区 */
    }

</style>
""", unsafe_allow_html=True)

# ------------------ 2. 功能逻辑 (Backend) ------------------
def extract_text_from_bytes(file_obj, filename):
    if '.' in filename: ext = filename.split('.')[-1].lower()
    else: ext = 'txt'
    text = ""
    try:
        if ext == 'docx':
            doc = Document(file_obj)
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except: return ""
    
    if ext in ['srt', 'vtt', 'ass']:
        text = re.sub(r"<.*?>", "", text)
        text = re.sub(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", "", text)
    return text

def process_words(all_text, mode, min_len, filter_set=None):
    TOKEN_RE = re.compile(r"[A-Za-z-]+")
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in TOKEN_RE.findall(all_text) if w]
    lemmatized = []
    
    if mode == "spacy" and nlp_spacy:
        # 分块处理防止内存溢出
        chunks = [cleaned[i:i + 50000] for i in range(0, len(cleaned), 50000)]
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

# ------------------ 3. 自定义组件 (Copy Button) ------------------
def render_copy_button(text_content):
    safe_text = json.dumps(text_content)
    # 匹配 Teal 主题的复制按钮
    html_code = f"""
    <script>
    function copyText() {{
        const text = {safe_text};
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        const btn = document.getElementById("copy_btn");
        btn.innerHTML = "✅ 已复制 (Copied!)";
        btn.style.background = "#059669";
        setTimeout(() => {{ 
            btn.innerHTML = "📋 一键复制结果 (Copy)"; 
            btn.style.background = "linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%)";
        }}, 2000);
    }}
    </script>
    <button id="copy_btn" onclick="copyText()" style="
        width: 100%; padding: 12px; 
        background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%); 
        color: white; border: none; border-radius: 12px; 
        font-family: sans-serif; font-weight: 700; cursor: pointer;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.2); transition: all 0.3s;">
        📋 一键复制结果 (Copy)
    </button>
    """
    components.html(html_code, height=60)

# ------------------ 4. 主界面布局 ------------------

# 侧边栏
with st.sidebar:
    # Logo 区域
    st.markdown("""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
            <div style="width:36px; height:36px; background:linear-gradient(135deg, #2DD4BF, #0F766E); border-radius:8px; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; box-shadow:0 0 15px rgba(45,212,191,0.4);">V</div>
            <h2 style="margin:0; font-size:1.2rem; color:#0f172a;">VocabMaster</h2>
        </div>
    """, unsafe_allow_html=True)
    
    menu = st.radio("MENU", ["⚡ 智能工作台", "📚 公共词书库", "👤 个人中心"], label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("<div style='background:#f0fdfa; padding:12px; border-radius:8px; color:#0f766e; font-size:0.85rem;'><b>💡 Pro Tips:</b><br>使用 Spacy 引擎可获得更精准的词形还原 (Better Lemmatization).</div>", unsafe_allow_html=True)

# 顶部导航栏 (模拟)
c_title, c_user = st.columns([3, 1])
with c_title:
    if "工作台" in menu:
        st.title("智能生词提取")
        st.caption("AI 赋能，一键生成专属词书 (Workbench)")
    elif "词书库" in menu:
        st.title("公共词书库")
        st.caption("发现优质语料，开启学习之旅 (Library)")
    else:
        st.title("个人中心")

with c_user:
    # 模拟用户头像
    st.markdown("""
    <div style="display:flex; justify-content:flex-end; align-items:center; gap:10px; padding-top:10px;">
        <span style="background:white; padding:4px 10px; border-radius:20px; border:1px solid #e2e8f0; font-size:12px; font-weight:bold; color:#475569;">🚀 Free Plan</span>
        <img src="https://api.dicebear.com/7.x/notionists/svg?seed=Felix" style="width:40px; height:40px; border-radius:50%; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# === ⚡ 智能工作台 ===
if "工作台" in menu:
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    
    # 采用 1:2.5 的布局复刻 HTML
    col_config, col_main = st.columns([1, 2.5], gap="medium")
    
    # 左侧：配置卡片
    with col_config:
        with st.container(border=True): # 实际上被 CSS 样式化为白色卡片
            st.markdown("##### 🛠️ 提取配置")
            
            st.caption("AI 引擎 (ENGINE)")
            nlp_mode = st.selectbox("Engine", ["nltk (快速)", "spacy (精准)"], label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption("排序方式 (SORT)")
            sort_order = st.selectbox("Sort", ["按文本出现顺序", "按字母 A-Z", "随机打乱"], label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption(f"最短词长 (MIN LENGTH)")
            min_len = st.slider("Min Len", 2, 15, 3, label_visibility="collapsed")
            
            st.markdown("---")
            st.markdown("##### 🛡️ 熟词屏蔽")
            # 预置词库
            selected_presets = st.multiselect(
                "选择预置库",
                options=list(PRESET_WORDLISTS.keys()),
                default=[],
                label_visibility="collapsed",
                placeholder="选择要屏蔽的词汇等级..."
            )
            # 自定义上传
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            filter_file = st.file_uploader("上传自定义屏蔽表 (.txt)", type=['txt'], label_visibility="collapsed")
            if filter_file: st.caption(f"已加载: {filter_file.name}")

            # 处理 Filter
            filter_set = set()
            for p in selected_presets:
                path = PRESET_WORDLISTS[p]
                if os.path.exists(path):
                    with open(path,'r',encoding='utf-8') as f: filter_set.update(f.read().splitlines())
            if filter_file:
                filter_set.update(filter_file.getvalue().decode('utf-8', errors='ignore').splitlines())

    # 右侧：主操作区
    with col_main:
        with st.container(border=True):
            st.markdown("""
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <span style="font-size:12px; font-weight:bold; color:#94a3b8; letter-spacing:1px;">INPUT SOURCE</span>
            </div>
            """, unsafe_allow_html=True)
            
            input_text = st.text_area("Input", height=200, placeholder="在此粘贴文章、字幕文本、歌词...\n或者点击下方虚线框上传文件", label_visibility="collapsed")
            
            uploaded_files = st.file_uploader("或拖拽文件到此处 (支持 .srt, .docx, .txt)", type=['txt','srt','ass','docx'], accept_multiple_files=True, label_visibility="collapsed")

            col_act_1, col_act_2 = st.columns([3, 1])
            with col_act_2:
                st.markdown("<br>", unsafe_allow_html=True)
                start_btn = st.button("🚀 开始智能提取", type="primary", use_container_width=True)

        # 处理逻辑
        if start_btn:
            full_text = input_text
            if uploaded_files:
                for f in uploaded_files:
                    full_text += "\n" + extract_text_from_bytes(f, f.name)
            
            if not full_text.strip():
                st.warning("⚠️ 请先输入文本或上传文件")
            else:
                with st.spinner("AI 正在分析语义与词形..."):
                    mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
                    words = process_words(full_text, mode_key, min_len, filter_set)
                    
                    if sort_order == "按字母 A-Z": words.sort()
                    elif sort_order == "随机打乱": random.shuffle(words)
                    
                    st.session_state.result_words = words
                    # 强制刷新以显示结果
                    st.rerun()

    # 结果展示 (如果有)
    if st.session_state.result_words:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            words = st.session_state.result_words
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3 style="margin:0;">🎉 提取结果</h3>
                <span style="background:#dcfce7; color:#166534; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:bold;">共 {len(words)} 词</span>
            </div>
            """, unsafe_allow_html=True)
            
            content_str = "\n".join(words)
            # 使用 text_area 展示结果，方便查看
            st.text_area("Result", value=content_str, height=150, label_visibility="collapsed")
            
            c_copy, c_dl = st.columns([1, 1])
            with c_copy:
                render_copy_button(content_str)
            with c_dl:
                 st.download_button("📦 下载结果 (.txt)", content_str, "vocab.txt", "text/plain", use_container_width=True)

# === 📚 公共词书库 ===
elif "词书库" in menu:
    
    # 搜索条
    search_col, _ = st.columns([1, 2])
    with search_col:
        st.text_input("Search", placeholder="🔍 搜索词书...", label_visibility="collapsed")

    # 模拟数据
    books = [
        {"title": "考研大纲", "sub": "2026版", "color": "#FDE68A", "text": "#451a03", "badge": "HOT", "count": 5500},
        {"title": "CET-4", "sub": "高频核心", "color": "#A7F3D0", "text": "#064e3b", "badge": "核心", "count": 2400},
        {"title": "托福词汇", "sub": "绿宝书", "color": "#BFDBFE", "text": "#1e3a8a", "badge": "留学", "count": 3800},
        {"title": "经济学人", "sub": "精选词汇", "color": "#FECACA", "text": "#7f1d1d", "badge": "高阶", "count": 1200},
        {"title": "老友记", "sub": "S01-S10", "color": "#DDD6FE", "text": "#4c1d95", "badge": "趣味", "count": 4500},
    ]

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Grid 布局展示书籍
    cols = st.columns(5) # 5列布局
    
    for i, book in enumerate(books):
        with cols[i % 5]:
            # 使用 HTML 注入生成 3D 书籍
            st.markdown(f"""
            <div class="book-container">
                <div class="book-3d" style="background-color: {book['color']}; color: {book['text']};">
                    <div class="book-spine"></div>
                    <div class="book-badge">{book['badge']}</div>
                    <h3 style="font-size:1.1rem; margin-top:20px; line-height:1.2; color:{book['text']}">{book['title']}</h3>
                    <p style="font-size:0.8rem; opacity:0.8; margin-top:5px; color:{book['text']}">{book['sub']}</p>
                    <div style="margin-top:auto; font-size:0.75rem; font-weight:bold; opacity:0.6;">{book['count']} 词</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 简单的下载按钮模拟
            st.button(f"下载", key=f"dl_{i}", use_container_width=True)

# === 个人中心 ===
else:
    st.info("🚧 个人中心正在施工中... (Coming Soon)")
