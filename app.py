这是一个非常关键的修复。

**为什么之前的代码无法读取 Library 了？**
原因是在上一次 UI 重构（变为 Teal/Slate 风格）时，为了展示 3D 书籍的视觉效果，我暂时使用了\*\*静态的模拟数据（Mock Data）\*\*替换了原本读取本地/GitHub 文件的逻辑。

下面的代码**完美融合**了三个部分：

1.  **新 UI 风格**（Teal/Slate + 3D 书籍）。
2.  **新手指引模块**（你提供的代码）。
3.  **动态逻辑回归**（重新读取 `library` 文件夹，并支持上传到 GitHub）。

请使用以下完整代码覆盖 `app.py`：

```python
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

# 确保目录存在
for d in [WORDLIST_DIR, LIBRARY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

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

# ------------------ 1. 页面配置 & CSS 设计系统 ------------------
st.set_page_config(
    page_title="VocabMaster", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    .stApp { background-color: #F8FAFC; font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif; color: #1e293b; }
    h1, h2, h3, h4 { font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; color: #0f172a; }
    
    /* 侧边栏 */
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; }
    section[data-testid="stSidebar"] > div { padding-top: 2rem; }

    /* 卡片容器 */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border: 1px solid #e2e8f0; border-radius: 16px; background-color: #ffffff;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05); padding: 24px;
    }

    /* 按钮样式 */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%); color: white; border: none;
        border-radius: 12px; padding: 0.6rem 1.5rem; font-weight: 700;
        box-shadow: 0 4px 12px rgba(15, 118, 110, 0.2); transition: all 0.3s;
    }
    div.stButton > button[kind="primary"]:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(15, 118, 110, 0.3); }
    
    /* 输入框 */
    .stSelectbox > div > div, .stTextInput > div > div, .stNumberInput > div > div {
        background-color: #F8FAFC; border: 1px solid #cbd5e1; border-radius: 10px;
    }
    [data-testid="stFileUploader"] {
        background-color: #F8FAFC; border: 2px dashed #cbd5e1; border-radius: 16px; padding: 20px; text-align: center;
    }

    /* 3D 书籍特效 */
    .book-container { perspective: 1000px; margin-bottom: 20px; }
    .book-3d {
        width: 100%; aspect-ratio: 3/4; border-radius: 4px 12px 12px 4px; position: relative;
        transform-style: preserve-3d; transition: transform 0.3s ease; box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
        cursor: pointer; display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; padding: 15px; overflow: hidden;
    }
    .book-3d:hover { transform: translateY(-8px) rotateY(-5deg) scale(1.02); box-shadow: 10px 15px 25px rgba(0,0,0,0.15); }
    .book-spine {
        position: absolute; left: 0; top: 0; bottom: 0; width: 12px;
        background: linear-gradient(90deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 100%);
        z-index: 10; border-right: 1px solid rgba(0,0,0,0.05);
    }
    .book-badge {
        position: absolute; top: 12px; left: 16px; background: rgba(255,255,255,0.9);
        backdrop-filter: blur(4px); padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 800; color: #1e293b; z-index: 20;
    }
    header[data-testid="stHeader"] { background: transparent; }
    .stMain { margin-top: -60px; }
</style>
""", unsafe_allow_html=True)

# ------------------ 2. 核心功能函数 ------------------

# GitHub 上传功能 (从原版恢复)
def save_to_github_library(filename, content, title, desc):
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("🔒 未配置 GitHub Token，无法上传到云端。仅保存到本地。")
            # 即使失败也保存到本地
            with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f:
                f.write(content)
            return

        token = st.secrets["GITHUB_TOKEN"]
        username = st.secrets["GITHUB_USERNAME"]
        repo_name = st.secrets["GITHUB_REPO"]
        
        g = Github(token)
        repo = g.get_repo(f"{username}/{repo_name}")
        
        # 1. 上传内容文件
        library_path = f"library/{filename}"
        try:
            contents = repo.get_contents(library_path)
            repo.update_file(library_path, f"Update {filename}", content, contents.sha)
        except:
            repo.create_file(library_path, f"Create {filename}", content)

        # 2. 更新 info.json
        info_path = "library/info.json"
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
            
        # 3. 同步到本地
        with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f:
            f.write(content)
        
        local_info_path = os.path.join(LIBRARY_DIR, "info.json")
        try:
            with open(local_info_path, "r", encoding="utf-8") as f: local_info = json.load(f)
        except: local_info = {}
        
        local_info[filename] = info_data[filename]
        with open(local_info_path, "w", encoding="utf-8") as f:
            json.dump(local_info, f, indent=2, ensure_ascii=False)

        st.toast("✅ 发布成功！已同步至云端。", icon="🎉")
        time.sleep(1.5)
        st.rerun()
        
    except Exception as e:
        # 降级处理：保存到本地
        with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f:
            f.write(content)
        st.warning(f"云端同步失败 ({e})，但已保存至本地 Library。")
        time.sleep(1.5)
        st.rerun()

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

def render_copy_button(text_content, key_suffix=""):
    safe_text = json.dumps(text_content)
    html_code = f"""
    <script>
    function copyText_{key_suffix}() {{
        const text = {safe_text};
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        const btn = document.getElementById("copy_btn_{key_suffix}");
        btn.innerHTML = "✅ 已复制";
        btn.style.background = "#059669";
        setTimeout(() => {{ 
            btn.innerHTML = "📋 一键复制"; 
            btn.style.background = "linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%)";
        }}, 2000);
    }}
    </script>
    <button id="copy_btn_{key_suffix}" onclick="copyText_{key_suffix}()" style="
        width: 100%; padding: 10px; 
        background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%); 
        color: white; border: none; border-radius: 8px; 
        font-family: sans-serif; font-weight: 600; cursor: pointer;
        box-shadow: 0 4px 10px rgba(15, 118, 110, 0.2); transition: all 0.3s;">
        📋 一键复制
    </button>
    """
    components.html(html_code, height=50)

# ------------------ 3. 主界面布局 ------------------

with st.sidebar:
    st.markdown("""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
            <div style="width:36px; height:36px; background:linear-gradient(135deg, #2DD4BF, #0F766E); border-radius:8px; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; box-shadow:0 0 15px rgba(45,212,191,0.4);">V</div>
            <h2 style="margin:0; font-size:1.2rem; color:#0f172a;">VocabMaster</h2>
        </div>
    """, unsafe_allow_html=True)
    
    menu = st.radio("MENU", ["⚡ 智能工作台", "📚 公共词书库", "👤 个人中心"], label_visibility="collapsed")
    
    st.markdown("---")
    st.markdown("<div style='background:#f0fdfa; padding:12px; border-radius:8px; color:#0f766e; font-size:0.85rem;'><b>💡 Pro Tips:</b><br>使用 Spacy 引擎可获得更精准的词形还原 (Better Lemmatization).</div>", unsafe_allow_html=True)

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
    st.markdown("""
    <div style="display:flex; justify-content:flex-end; align-items:center; gap:10px; padding-top:10px;">
        <span style="background:white; padding:4px 10px; border-radius:20px; border:1px solid #e2e8f0; font-size:12px; font-weight:bold; color:#475569;">🚀 Free Plan</span>
        <img src="https://api.dicebear.com/7.x/notionists/svg?seed=Felix" style="width:40px; height:40px; border-radius:50%; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
    </div>
    """, unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# === ⚡ 智能工作台 ===
if "工作台" in menu:
    
    # --- 插入：资源导航 (用户提供代码) ---
    with st.expander("📖 新手指南 & 宝藏资源库 (点击展开)", expanded=False):
        t1, t2, t3, t4 = st.tabs(["💡 操作指引", "🎬 影视字幕", "📚 原著阅读", "🎧 听力素材"])
        
        with t1:
            st.markdown("""
            <div style="padding:5px;">
            <h5 style="margin-top:0">🚀 四步制作专属词书：</h5>
            <ol>
                <li><b>准备素材</b>：从右侧标签页下载 <code>.srt</code> 字幕或 <code>.txt</code> 电子书。</li>
                <li><b>清洗设置</b>：在下方【设置提取规则】中，选择<b>“预置熟词库”</b>或上传自定义熟词表（非常重要！能屏蔽掉 is, the 等简单词）。</li>
                <li><b>智能提取</b>：将文件拖入上传区，AI 自动完成去重、词形还原（Run/Ran/Running → Run）。</li>
                <li><b>闭环学习</b>：点击生成的<b>“一键复制”</b>按钮，跳转扇贝网批量制卡，或导出词书。</li>
            </ol>
            </div>
            """, unsafe_allow_html=True)
            
        with t2:
            st.info("💡 字幕文件是提取口语词汇的最佳材料。下载后无需转换，直接拖入本工具。")
            c1, c2 = st.columns(2)
            c1.markdown("🎯 **[伪射手网 (Assrt)](https://assrt.net/)**\n<small>老牌站点，资源最全，支持中英双语。</small>", unsafe_allow_html=True)
            c1.markdown("📺 **[字幕库 (Zimuku)](http://zimuku.org/)**\n<small>美剧、日剧更新速度极快。</small>", unsafe_allow_html=True)
            c1.markdown("⚡ **[Addic7ed](https://www.addic7ed.com/)**\n<small>美剧生肉更新最快的地方，适合高阶学习者。</small>", unsafe_allow_html=True)
            
            c2.markdown("💎 **[SubHD](https://subhd.tv/)**\n<small>界面清爽，高清影视字幕首选。</small>", unsafe_allow_html=True)
            c2.markdown("🌎 **[OpenSubtitles](https://www.opensubtitles.org/)**\n<small>全球最大字幕库，寻找纯英文字幕首选。</small>", unsafe_allow_html=True)
            c2.markdown("🎞️ **[YIFY Subtitles](https://yifysubtitles.ch/)**\n<small>专门针对电影的高质量英文字幕。</small>", unsafe_allow_html=True)

        with t3:
            st.success("📚 推荐下载 .txt 或 .epub (需转txt) 格式。")
            c1, c2 = st.columns(2)
            c1.markdown("🏛️ **[Project Gutenberg](https://www.gutenberg.org/)**\n<small>拥有7万+免费公版电子书，英文原著的大宝库。</small>", unsafe_allow_html=True)
            c1.markdown("📖 **[ManyBooks](https://manybooks.net/)**\n<small>排版精美，分类详细，下载体验好。</small>", unsafe_allow_html=True)
            
            c2.markdown("📰 **[Global Times](https://www.globaltimes.cn/)**\n<small>国产英文媒体，用词贴近时政，适合备考。</small>", unsafe_allow_html=True)
            c2.markdown("🧠 **[Scientific American](https://www.scientificamerican.com/)**\n<small>高阶科普文章，托福/雅思/GRE 阅读同源素材。</small>", unsafe_allow_html=True)

        with t4:
            st.warning("🎧 技巧：下载 Transcript (文稿) 提取单词，学完再去听。")
            c1, c2 = st.columns(2)
            c1.markdown("🔴 **[TED Talks](https://www.ted.com/)**\n<small>思想盛宴，每个视频都自带多语言文稿。</small>", unsafe_allow_html=True)
            c1.markdown("🇺🇸 **[VOA Learning English](https://learningenglish.voanews.com/)**\n<small>经典分级听力材料，含纯正文稿。</small>", unsafe_allow_html=True)
            
            c2.markdown("🇬🇧 **[BBC Learning English](https://www.bbc.co.uk/learningenglish/)**\n<small>英式英语金牌教程，6 Minute English 必听。</small>", unsafe_allow_html=True)
            c2.markdown("🎓 **[Coursera](https://www.coursera.org/)**\n<small>学习专业课（计算机/商科）的最好方式。</small>", unsafe_allow_html=True)
    # ------------------------------------------------

    if 'result_words' not in st.session_state: st.session_state.result_words = []
    
    col_config, col_main = st.columns([1, 2.5], gap="medium")
    
    with col_config:
        with st.container(border=True):
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
            selected_presets = st.multiselect("选择预置库", options=list(PRESET_WORDLISTS.keys()), default=[], label_visibility="collapsed")
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            filter_file = st.file_uploader("上传自定义屏蔽表 (.txt)", type=['txt'], label_visibility="collapsed")

            filter_set = set()
            for p in selected_presets:
                if os.path.exists(PRESET_WORDLISTS[p]):
                    with open(PRESET_WORDLISTS[p],'r',encoding='utf-8') as f: filter_set.update(f.read().splitlines())
            if filter_file:
                filter_set.update(filter_file.getvalue().decode('utf-8', errors='ignore').splitlines())

    with col_main:
        with st.container(border=True):
            st.markdown("""<div style="display:flex; justify-content:space-between; margin-bottom:10px;"><span style="font-size:12px; font-weight:bold; color:#94a3b8; letter-spacing:1px;">INPUT SOURCE</span></div>""", unsafe_allow_html=True)
            input_text = st.text_area("Input", height=200, placeholder="在此粘贴文章、字幕文本、歌词...\n或者点击下方虚线框上传文件", label_visibility="collapsed")
            uploaded_files = st.file_uploader("或拖拽文件到此处 (支持 .srt, .docx, .txt)", type=['txt','srt','ass','docx'], accept_multiple_files=True, label_visibility="collapsed")

            col_act_1, col_act_2 = st.columns([3, 1])
            with col_act_2:
                st.markdown("<br>", unsafe_allow_html=True)
                start_btn = st.button("🚀 开始智能提取", type="primary", use_container_width=True)

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
                    st.rerun()

    if st.session_state.result_words:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            words = st.session_state.result_words
            content_str = "\n".join(words)
            
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3 style="margin:0;">🎉 提取结果</h3>
                <span style="background:#dcfce7; color:#166534; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:bold;">共 {len(words)} 词</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.text_area("Result", value=content_str, height=150, label_visibility="collapsed")
            
            c_copy, c_dl, c_pub = st.columns([1, 1, 1])
            with c_copy: render_copy_button(content_str)
            with c_dl: st.download_button("📦 下载结果 (.txt)", content_str, "vocab.txt", "text/plain", use_container_width=True)
            with c_pub:
                with st.popover("☁️ 发布到社区库"):
                    st.markdown("**分享你的词书**")
                    with st.form("pub_form"):
                        name = st.text_input("文件名 (英文, e.g. friends_s1.txt)", value=f"list_{int(time.time())}.txt")
                        title = st.text_input("标题 (e.g. 老友记第一季)")
                        desc = st.text_area("简介 (e.g. 包含前10集生词)")
                        if st.form_submit_button("确认发布"):
                            if name.endswith(".txt"): 
                                save_to_github_library(name, content_str, title, desc)
                            else:
                                st.error("文件名必须以 .txt 结尾")

# === 📚 公共词书库 ===
elif "词书库" in menu:
    
    search_col, _ = st.columns([1, 2])
    with search_col:
        search_q = st.text_input("Search", placeholder="🔍 搜索词书...", label_visibility="collapsed").lower()

    # --- 修复：重新读取本地/云端文件 (不再使用静态数据) ---
    try:
        with open(os.path.join(LIBRARY_DIR, "info.json"), "r", encoding="utf-8") as f: book_info = json.load(f)
    except: book_info = {}
    
    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    visible = [f for f in files if search_q in f.lower() or search_q in book_info.get(f, {}).get("title", "").lower()]
    
    # 颜色池，用于循环分配给书籍
    palettes = [
        {"bg": "#FDE68A", "txt": "#451a03"}, # Amber
        {"bg": "#A7F3D0", "txt": "#064e3b"}, # Emerald
        {"bg": "#BFDBFE", "txt": "#1e3a8a"}, # Blue
        {"bg": "#FECACA", "txt": "#7f1d1d"}, # Red
        {"bg": "#DDD6FE", "txt": "#4c1d95"}, # Violet
        {"bg": "#E2E8F0", "txt": "#0f172a"}, # Slate
    ]

    if not visible:
        st.info("📭 暂无数据，去工作台制作第一个词书吧！")
    else:
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns(5)
        for i, f in enumerate(visible):
            meta = book_info.get(f, {})
            title = meta.get("title", f)
            desc = meta.get("desc", "暂无描述")
            
            # 读取词数
            try:
                with open(os.path.join(LIBRARY_DIR, f), 'r', encoding='utf-8') as _f:
                    cnt = len(_f.read().splitlines())
            except: cnt = "?"
            
            color = palettes[i % len(palettes)]
            
            with cols[i % 5]:
                # 3D 书籍渲染 (Dynamic)
                st.markdown(f"""
                <div class="book-container">
                    <div class="book-3d" style="background-color: {color['bg']}; color: {color['txt']};">
                        <div class="book-spine"></div>
                        <div class="book-badge">TXT</div>
                        <h3 style="font-size:1.1rem; margin-top:20px; line-height:1.2; color:{color['txt']}; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">{title}</h3>
                        <p style="font-size:0.75rem; opacity:0.8; margin-top:5px; color:{color['txt']}; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;">{desc}</p>
                        <div style="margin-top:auto; font-size:0.75rem; font-weight:bold; opacity:0.6;">{cnt} 词</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 操作按钮
                with st.popover("下载/预览", use_container_width=True):
                    st.markdown(f"**{title}**")
                    try:
                        with open(os.path.join(LIBRARY_DIR, f), 'r', encoding='utf-8') as _f: c = _f.read()
                        render_copy_button(c, f"lib_{i}")
                        st.download_button("⬇️ 下载", c, f, "text/plain")
                        st.text_area("预览", c, height=200)
                    except: st.error("文件读取失败")

# === 个人中心 ===
else:
    st.info("🚧 个人中心正在施工中... (Coming Soon)")
```
