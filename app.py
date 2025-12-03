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
LIBRARY_DIR = "library"
for d in [WORDLIST_DIR, LIBRARY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# 确保演示数据存在
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

# ------------------ 1. 核心 CSS 设计系统 (Pixel-Perfect 还原) ------------------
st.set_page_config(page_title="VocabMaster", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* 引入参考图同款字体 */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    /* --- 全局重置 --- */
    .stApp {
        background-color: #F8FAFC; /* Slate-50 */
        font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
        color: #1e293b;
    }
    
    /* 隐藏 Streamlit 默认 Header 和 Footer */
    header[data-testid="stHeader"] { background: transparent; pointer-events: none; }
    footer { display: none; }
    .stMain { margin-top: -60px; } /* 拉起内容 */

    /* --- 侧边栏 (Sidebar) 1:1 还原 --- */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #f1f5f9;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
        width: 280px !important;
    }
    /* Logo 区域 */
    .logo-box {
        display: flex; align-items: center; gap: 12px; padding: 20px 10px; margin-bottom: 20px;
    }
    .logo-icon {
        width: 40px; height: 40px; 
        background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%);
        border-radius: 10px; display: flex; align-items: center; justify-content: center;
        color: white; font-weight: 800; font-size: 20px;
        box-shadow: 0 0 15px rgba(15, 118, 110, 0.3);
    }
    .logo-text { font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; }

    /* --- 通用组件样式 --- */
    
    /* 白色卡片 (替代 st.container) */
    .card-container {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 24px; /* 更大的圆角 */
        padding: 24px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    
    /* 标题样式 */
    h1, h2, h3 { font-family: 'Plus Jakarta Sans', sans-serif; color: #0f172a; letter-spacing: -0.02em; }
    
    /* 自定义按钮 (Primary - Teal) */
    div.stButton > button[kind="primary"] {
        background: #0f172a; /* Dark Slate based on ref */
        color: white; border: none; width: 100%;
        border-radius: 16px; padding: 0.75rem 1.5rem; 
        font-weight: 700; font-size: 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
        display: flex; align-items: center; justify-content: center; gap: 8px;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #0F766E; /* Hover to Teal */
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(15, 118, 110, 0.3);
    }

    /* 输入框美化 (去除默认边框，融入卡片) */
    .stTextInput > div > div, .stSelectbox > div > div, .stNumberInput > div > div {
        background-color: #F8FAFC; border: 1px solid #e2e8f0; border-radius: 12px; height: 48px;
    }
    .stTextInput > div > div:focus-within { border-color: #0F766E; box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1); }
    
    /* 大文本域 (Text Area) - 模仿参考图的无边框设计 */
    .stTextArea > div > div {
        background-color: transparent; border: none; border-bottom: 1px dashed #e2e8f0;
        border-radius: 0; padding: 0; font-family: 'JetBrains Mono', monospace;
    }
    .stTextArea textarea { font-size: 14px; line-height: 1.6; color: #334155; }
    
    /* 文件上传区 (Dotted) */
    [data-testid="stFileUploader"] {
        background-color: #F8FAFC; border: 2px dashed #cbd5e1; border-radius: 16px; padding: 20px;
    }
    [data-testid="stFileUploader"] section { background-color: transparent; }

    /* 顶部 Glass Header */
    .glass-header {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255,255,255,0.5);
        padding: 16px 32px;
        display: flex; justify-content: space-between; align-items: center;
        margin: -60px -60px 20px -60px; /* 抵消 stMain 的 margin */
        position: sticky; top: 0; z-index: 999;
    }
    
    /* 3D 书籍样式 */
    .book-3d {
        width: 100%; aspect-ratio: 3/4; border-radius: 4px 12px 12px 4px; position: relative;
        transform-style: preserve-3d; transition: transform 0.3s ease; box-shadow: 0 10px 30px -5px rgba(0,0,0,0.1);
        cursor: pointer; display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; padding: 15px; overflow: hidden; background: white;
    }
    .book-3d:hover { transform: translateY(-8px) rotateY(-5deg) scale(1.02); box-shadow: 0 20px 40px -5px rgba(0,0,0,0.2); }
    .book-texture { position: absolute; inset: 0; opacity: 0.1; background-image: radial-gradient(#000 1px, transparent 1px); background-size: 4px 4px; }
    
    /* Tabs 样式优化 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; border-bottom: none; }
    .stTabs [data-baseweb="tab"] {
        background-color: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 8px 16px; font-weight: 600; color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f172a; color: white; border: none; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
    }
    
    /* Expander 样式 */
    .streamlit-expanderHeader { background-color: white; border-radius: 12px; font-weight: 600; border: 1px solid #e2e8f0; }
    [data-testid="stExpander"] { border: none; box-shadow: none; background: transparent; }

</style>
""", unsafe_allow_html=True)

# ------------------ 2. 逻辑层 ------------------
def save_to_github_library(filename, content, title, desc):
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            # 本地降级模式
            with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f: f.write(content)
            # 更新本地 info
            local_info_path = os.path.join(LIBRARY_DIR, "info.json")
            try: 
                with open(local_info_path, "r", encoding="utf-8") as f: local_info = json.load(f)
            except: local_info = {}
            local_info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
            with open(local_info_path, "w", encoding="utf-8") as f: json.dump(local_info, f, indent=2, ensure_ascii=False)
            st.toast("⚠️ 无 GitHub Token，已保存至本地 Library。", icon="📂")
            time.sleep(1)
            st.rerun()
            return

        token = st.secrets["GITHUB_TOKEN"]
        g = Github(token)
        repo = g.get_repo(f"{st.secrets['GITHUB_USERNAME']}/{st.secrets['GITHUB_REPO']}")
        
        # 上传文件
        try: repo.create_file(f"library/{filename}", f"Create {filename}", content)
        except: repo.update_file(f"library/{filename}", f"Update {filename}", content, repo.get_contents(f"library/{filename}").sha)

        # 更新索引
        info_path = "library/info.json"
        try:
            c = repo.get_contents(info_path)
            info = json.loads(c.decoded_content.decode())
            info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
            repo.update_file(info_path, "Update info", json.dumps(info, ensure_ascii=False, indent=2), c.sha)
        except:
            info = {filename: {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}}
            repo.create_file(info_path, "Init info", json.dumps(info, ensure_ascii=False, indent=2))
        
        # 同时写本地，保证流畅
        with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f: f.write(content)
        st.toast("✅ 云端同步成功！", icon="🎉")
        time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"操作失败: {e}")

def extract_text_from_bytes(file_obj, filename):
    try:
        ext = filename.split('.')[-1].lower()
        if ext == 'docx':
            return "\n".join([p.text for p in Document(file_obj).paragraphs if p.text.strip()])
        raw = file_obj.read()
        return raw.decode(chardet.detect(raw)['encoding'] or 'utf-8', errors='ignore')
    except: return ""

def process_words(text, mode, min_len, filter_set=None):
    # 简单的进度条模拟
    bar = st.progress(0)
    for i in range(50):
        time.sleep(0.01)
        bar.progress(i + 1)
    
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in re.findall(r"[A-Za-z-]+", text) if w]
    lemmatized = []
    
    if mode == "spacy" and nlp_spacy:
        doc = nlp_spacy(" ".join(cleaned[:100000])) # Limit for demo speed
        lemmatized = [t.lemma_.lower() for t in doc if t.lemma_.isalpha()]
    else:
        l = WordNetLemmatizer()
        lemmatized = [l.lemmatize(w) for w in cleaned]

    bar.progress(80)
    seen, final = set(), []
    stops = set(stopwords.words('english'))
    
    for w in lemmatized:
        if len(w) >= min_len and w not in stops and (not filter_set or w not in filter_set) and w not in seen:
            seen.add(w)
            final.append(w)
    
    bar.progress(100)
    time.sleep(0.2)
    bar.empty()
    return final

def copy_btn(text):
    safe = json.dumps(text)
    components.html(f"""
    <button onclick="navigator.clipboard.writeText({safe}).then(()=>this.innerHTML='✅ 已复制').catch(()=>this.innerHTML='❌ 失败')" 
    style="width:100%;padding:10px;background:linear-gradient(135deg,#2DD4BF,#0F766E);color:white;border:none;border-radius:12px;font-weight:bold;cursor:pointer;">
    📋 一键复制结果
    </button>""", height=50)

# ------------------ 3. 布局实现 ------------------

# === 侧边栏 ===
with st.sidebar:
    st.markdown("""
        <div class="logo-box">
            <div class="logo-icon">V</div>
            <div class="logo-text">VocabMaster</div>
        </div>
    """, unsafe_allow_html=True)
    
    nav = st.radio("NAV", ["⚡ 智能工作台", "📚 公共词书库", "👤 个人中心"], label_visibility="collapsed")
    st.markdown("---")
    st.info("💡 **Pro Tip**: 字幕文件直接拖入，无需转换格式。")

# === 顶部 Glass Header ===
st.markdown("""
<div class="glass-header">
    <div>
        <h3 style="margin:0; font-weight:800; color:#0f172a;">Dashboard</h3>
        <p style="margin:0; font-size:12px; color:#64748b;">Welcome back, User</p>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
        <span style="background:white; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold; color:#0F766E; border:1px solid #ccfbf1;">🚀 Pro Plan</span>
        <img src="https://api.dicebear.com/7.x/notionists/svg?seed=Alex" style="width:36px; height:36px; border-radius:50%; border:2px solid white; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
    </div>
</div>
""", unsafe_allow_html=True)

# === 核心页面 ===
if "工作台" in nav:
    
    # 资源导航 (新手引导)
    with st.expander("📖 新手指南 & 资源库 (展开)", expanded=False):
        t1, t2, t3 = st.tabs(["💡 操作流程", "🎬 影视资源", "📚 阅读资源"])
        with t1:
            st.markdown("#### 🚀 四步制作专属词书")
            st.markdown("1. **配置**: 选择左侧过滤库（去除简单词）。\n2. **输入**: 粘贴文本或拖入字幕文件。\n3. **提取**: 点击提取按钮，AI 分析词形。\n4. **导出**: 复制结果到扇贝/Anki。")
        with t2:
            c1, c2 = st.columns(2)
            c1.markdown("- **[Assrt (伪射手)](https://assrt.net/)**: 字幕最全。\n- **[Zimuku](http://zimuku.org/)**: 更新快。")
            c2.markdown("- **[OpenSubtitles](https://www.opensubtitles.org/)**: 英文原版。")
        with t3:
            st.markdown("- **[Project Gutenberg](https://www.gutenberg.org/)**: 免费公版书。")

    # 主工作区：非对称布局 (4:8)
    col_left, col_right = st.columns([4, 8], gap="large")

    # 左侧：配置卡片
    with col_left:
        # 使用 CSS 类包装容器
        with st.container():
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            st.markdown("##### 🛠️ 提取配置 (Configuration)")
            
            st.caption("AI 引擎")
            eng = st.selectbox("Engine", ["nltk (Fast)", "spacy (Accurate)"], label_visibility="collapsed")
            
            st.caption("排序方式")
            sort = st.selectbox("Sort", ["按文本顺序", "A-Z 排序", "随机打乱"], label_visibility="collapsed")
            
            st.caption("最短词长")
            min_len = st.slider("Min Length", 2, 15, 3, label_visibility="collapsed")
            
            st.markdown("---")
            st.markdown("##### 🛡️ 熟词屏蔽 (Filter)")
            presets = st.multiselect("预置库", PRESET_WORDLISTS.keys(), default=[], label_visibility="collapsed", placeholder="选择要屏蔽的等级...")
            
            st.caption("上传自定义屏蔽词表")
            filter_f = st.file_uploader("Custom Filter", type=['txt'], label_visibility="collapsed")
            
            st.markdown('</div>', unsafe_allow_html=True) # End card

    # 右侧：输入卡片
    with col_right:
        with st.container():
            st.markdown('<div class="card-container" style="min-height:500px;">', unsafe_allow_html=True)
            
            # Header inside card
            st.markdown("""
            <div style="display:flex; justify-content:space-between; margin-bottom:16px;">
                <span style="font-weight:700; color:#334155;">📝 输入源 (Input Source)</span>
                <span style="font-size:12px; background:#f1f5f9; padding:2px 8px; rounded:4px;">支持 .txt .srt .docx</span>
            </div>
            """, unsafe_allow_html=True)
            
            # 文本域 + 上传组件 视觉融合
            txt_in = st.text_area("Input", height=200, placeholder="在此直接粘贴文章、字幕文本...\n或者使用下方的文件上传功能。", label_visibility="collapsed")
            files_in = st.file_uploader("File Upload", type=['txt','srt','ass','docx'], accept_multiple_files=True, label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Action Bar
            c_btn, c_info = st.columns([1, 1])
            with c_btn:
                run = st.button("🚀 开始智能提取 (Analyze)", type="primary")
            
            st.markdown('</div>', unsafe_allow_html=True) # End card
            
            # 处理逻辑
            if run:
                raw_text = txt_in
                if files_in:
                    for f in files_in: raw_text += "\n" + extract_text_from_bytes(f, f.name)
                
                if not raw_text.strip():
                    st.toast("❌ 请先输入内容！")
                else:
                    # 构建过滤集
                    f_set = set()
                    for p in presets:
                        with open(PRESET_WORDLISTS[p], 'r', encoding='utf-8') as f: f_set.update(f.read().splitlines())
                    if filter_f:
                        f_set.update(filter_f.getvalue().decode('utf-8', errors='ignore').splitlines())
                    
                    # 运行
                    res = process_words(raw_text, "spacy" if "spacy" in eng else "nltk", min_len, f_set)
                    if sort == "A-Z 排序": res.sort()
                    elif sort == "随机打乱": random.shuffle(res)
                    
                    st.session_state.res = res
                    st.rerun()

    # 结果展示区 (Full Width)
    if 'res' in st.session_state and st.session_state.res:
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown(f"### 🎉 提取结果 ({len(st.session_state.res)} 词)")
        
        final_str = "\n".join(st.session_state.res)
        st.text_area("Result", final_str, height=150)
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: copy_btn(final_str)
        with c2: st.download_button("📦 下载结果 (.txt)", final_str, "vocab.txt", use_container_width=True)
        with c3:
            with st.popover("☁️ 发布到社区库", use_container_width=True):
                with st.form("pub"):
                    name = st.text_input("Filename (.txt)", f"list_{int(time.time())}.txt")
                    title = st.text_input("Title")
                    desc = st.text_area("Description")
                    if st.form_submit_button("Submit"):
                        if name.endswith(".txt"): save_to_github_library(name, final_str, title, desc)
        st.markdown('</div>', unsafe_allow_html=True)

elif "词书库" in nav:
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    
    # 过滤器 + 搜索
    c_filter, c_search = st.columns([2, 1])
    with c_filter:
        st.write("🏷️ **标签筛选**")
        # 视觉上的 Tabs
        t_all, t_uni, t_hs, t_int = st.tabs(["全部", "大学/考研", "高中/高考", "兴趣/影视"])
    with c_search:
        q = st.text_input("Search", placeholder="🔍 搜索...", label_visibility="collapsed")
    
    # 动态读取 Library
    try:
        with open(os.path.join(LIBRARY_DIR, "info.json"), "r", encoding="utf-8") as f: meta = json.load(f)
    except: meta = {}
    
    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    visible = [f for f in files if q.lower() in f.lower() or q.lower() in meta.get(f, {}).get("title", "").lower()]
    
    st.markdown("<br>", unsafe_allow_html=True)
    if not visible:
        st.warning("📭 暂无数据。")
    else:
        cols = st.columns(4)
        colors = ["#FDE68A", "#A7F3D0", "#BFDBFE", "#FECACA", "#DDD6FE"]
        text_colors = ["#451a03", "#064e3b", "#1e3a8a", "#7f1d1d", "#4c1d95"]
        
        for i, f in enumerate(visible):
            info = meta.get(f, {})
            title = info.get("title", f)
            desc = info.get("desc", "No description")
            c_bg = colors[i % 5]
            c_tx = text_colors[i % 5]
            
            with cols[i % 4]:
                st.markdown(f"""
                <div class="book-3d" style="background-color:{c_bg}; color:{c_tx};">
                    <div class="book-texture"></div>
                    <h3 style="margin:0; font-size:18px; line-height:1.2;">{title}</h3>
                    <p style="font-size:12px; opacity:0.8; margin-top:8px;">{desc[:30]}...</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 操作区
                with st.expander("下载/预览"):
                    try:
                        with open(os.path.join(LIBRARY_DIR, f), 'r', encoding='utf-8') as _f: content = _f.read()
                        st.download_button("⬇️ Download", content, f)
                        st.code(content[:200] + "...", language="text")
                    except: st.error("Error reading file")
    
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("🚧 个人中心正在开发中...")
