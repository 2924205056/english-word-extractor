import streamlit as st
import io
import re
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
from PyPDF2 import PdfReader

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
        try:
            # 优先尝试加载高精度 Transformer 模型 (更厉害!)
            # 注意: 需要先在终端运行: python -m spacy download en_core_web_trf
            return spacy.load("en_core_web_trf")
        except OSError:
            try:
                # 降级方案: 中等模型
                return spacy.load("en_core_web_md")
            except OSError:
                # 保底方案: 小模型
                return spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            return None
    return None
download_nltk_resources()
nlp_spacy = load_spacy_model()

# ------------------ 1. 深度 CSS 设计系统 ------------------
st.set_page_config(page_title="VocabMaster", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    /* 全局背景与字体 */
    .stApp {
        background-color: #F8FAFC; 
        font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
        color: #1e293b;
    }
    
    /* 隐藏默认 Header */
    header[data-testid="stHeader"] { background: transparent; pointer-events: none; }
    .stMain { margin-top: -50px; }

    /* --- 侧边栏优化 --- */
    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #f1f5f9;
        box-shadow: 2px 0 15px rgba(0,0,0,0.01);
    }

    /* --- 核心：原生卡片容器美化 --- */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background-color: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        padding: 24px !important;
    }

    /* --- 组件样式 --- */
    /* 按钮 */
    div.stButton > button[kind="primary"] {
        background: #0f172a; color: white; border: none; width: 100%;
        border-radius: 12px; padding: 0.6rem 1.2rem; font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #334155; transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }

    /* 输入框/下拉框 */
    .stTextInput > div > div, .stSelectbox > div > div, .stNumberInput > div > div {
        background-color: #F8FAFC; border: 1px solid #cbd5e1; border-radius: 10px;
    }
    
    /* 文本域 (Text Area) */
    .stTextArea textarea {
        background-color: #F8FAFC; border: 1px solid #cbd5e1; border-radius: 10px;
        font-family: 'JetBrains Mono', monospace; font-size: 14px;
    }

    /* 文件上传区 (虚线风格) */
    [data-testid="stFileUploader"] {
        background-color: #F8FAFC; border: 2px dashed #94a3b8; border-radius: 12px;
        padding: 20px; transition: all 0.3s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #0F766E; background-color: #f0fdfa;
    }
    
    /* 顶部导航条 Glass */
    .top-nav {
        background: rgba(255,255,255,0.8); backdrop-filter: blur(10px);
        padding: 15px 20px; border-bottom: 1px solid #e2e8f0;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 20px; border-radius: 0 0 16px 16px;
    }

    /* 3D 书籍 */
    .book-3d {
        width: 100%; aspect-ratio: 3/4; border-radius: 6px 14px 14px 6px;
        position: relative; transition: transform 0.3s; cursor: pointer;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; padding: 10px; box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
    }
    .book-3d:hover { transform: translateY(-5px) scale(1.02); box-shadow: 8px 12px 25px rgba(0,0,0,0.15); }
    
</style>
""", unsafe_allow_html=True)

# ------------------ 2. 逻辑函数 ------------------
def save_to_github_library(filename, content, title, desc):
    try:
        # 1. 优先尝试云端上传
        if "GITHUB_TOKEN" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            g = Github(token)
            repo = g.get_repo(f"{st.secrets['GITHUB_USERNAME']}/{st.secrets['GITHUB_REPO']}")
            
            # 上传文件
            try: repo.create_file(f"library/{filename}", f"Create {filename}", content)
            except: repo.update_file(f"library/{filename}", f"Update {filename}", content, repo.get_contents(f"library/{filename}").sha)

            # 更新云端 info.json
            info_path = "library/info.json"
            try:
                c = repo.get_contents(info_path)
                info = json.loads(c.decoded_content.decode())
            except:
                info = {}
            
            info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
            
            try:
                repo.update_file(info_path, "Update info", json.dumps(info, ensure_ascii=False, indent=2), repo.get_contents(info_path).sha)
            except:
                repo.create_file(info_path, "Init info", json.dumps(info, ensure_ascii=False, indent=2))
                
            st.toast("✅ 云端发布成功！", icon="🎉")
        else:
            st.toast("⚠️ 无 GitHub Token，仅保存到本地。", icon="📂")

        # 2. 始终保存到本地 (用于即时显示)
        with open(os.path.join(LIBRARY_DIR, filename), "w", encoding="utf-8") as f: f.write(content)
        
        # 更新本地 info.json
        local_info_path = os.path.join(LIBRARY_DIR, "info.json")
        try: 
            with open(local_info_path, "r", encoding="utf-8") as f: local_info = json.load(f)
        except: local_info = {}
        
        local_info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
        
        with open(local_info_path, "w", encoding="utf-8") as f: json.dump(local_info, f, indent=2, ensure_ascii=False)

        st.rerun()

    except Exception as e:
        st.error(f"发布过程中出现错误: {e}")

def extract_text_from_bytes(file_obj, filename):
    try:
        ext = filename.split('.')[-1].lower()
        if ext == 'docx':
            return "\n".join([p.text for p in Document(file_obj).paragraphs if p.text.strip()])
        if ext == 'pdf':
            reader = PdfReader(file_obj)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        raw = file_obj.read()
        return raw.decode(chardet.detect(raw)['encoding'] or 'utf-8', errors='ignore')
    except: return ""

def get_wordnet_pos(treebank_tag):
    """将 Penn Treebank POS 标签映射为 WordNet POS，用于精准词形还原。"""
    if treebank_tag.startswith('J'): return wordnet.ADJ
    if treebank_tag.startswith('V'): return wordnet.VERB
    if treebank_tag.startswith('R'): return wordnet.ADV
    return wordnet.NOUN

def process_words(text, mode, min_len, filter_set=None):
    with st.spinner(f"正在词性还原中..."):
        word_counts = {}
        stops = set(stopwords.words('english'))

        # === Scheme A: Spacy (High Accuracy Mode) ===
        if mode == "spacy" and nlp_spacy:
            nlp_spacy.max_length = 2000000

            # 按句子边界分块，避免在单词中间切断
            chunk_size = 100000
            text_chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

            progress_bar = st.progress(0)

            for i, chunk in enumerate(text_chunks):
                progress_bar.progress((i + 1) / len(text_chunks))
                doc = nlp_spacy(chunk)

                for token in doc:
                    if (token.is_alpha and
                        not token.is_stop and
                        len(token.text) >= min_len and
                        token.pos_ in ['NOUN', 'VERB', 'ADJ', 'ADV']):

                        lemma = token.lemma_.lower()
                        if not re.match(r"^[a-z]+$", lemma):
                            continue
                        if filter_set and lemma in filter_set:
                            continue
                        word_counts[lemma] = word_counts.get(lemma, 0) + 1

            progress_bar.empty()

        # === Scheme B: NLTK (Fast / Fallback Mode) ===
        else:
            tokens = [w.lower() for w in re.findall(r"[A-Za-z-]+", text) if w]
            tagged = pos_tag(tokens)
            l = WordNetLemmatizer()

            for word, tag in tagged:
                clean = re.sub(r'[^a-z]', '', word)
                if len(clean) < min_len or clean in stops:
                    continue
                lemma = l.lemmatize(clean, get_wordnet_pos(tag))
                if not re.match(r"^[a-z]+$", lemma):
                    continue
                if filter_set and lemma in filter_set:
                    continue
                word_counts[lemma] = word_counts.get(lemma, 0) + 1

        # 按词频降序返回 [(word, count), ...]
        return sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
def copy_btn(text):
    safe_text = json.dumps(text)
    components.html(f"""
    <div style="display:flex; justify-content:center;">
        <button id="cbtn" onclick="copy()" style="
            background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
            color: white; border: none; padding: 10px 20px; border-radius: 8px;
            font-family: sans-serif; font-weight: bold; cursor: pointer; width: 100%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">📋 一键复制结果</button>
    </div>
    <script>
    function copy() {{
        navigator.clipboard.writeText({safe_text});
        document.getElementById("cbtn").innerText = "✅ 已复制！";
        setTimeout(() => {{ document.getElementById("cbtn").innerText = "📋 一键复制结果"; }}, 2000);
    }}
    </script>
    """, height=50)

# ------------------ 3. 页面布局 ------------------

# 侧边栏
with st.sidebar:
    st.markdown("""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px; padding:10px;">
            <div style="width:32px; height:32px; background:#0f172a; color:white; border-radius:6px; display:flex; align-items:center; justify-content:center; font-weight:bold;">V</div>
            <h3 style="margin:0; font-size:18px;">VocabMaster</h3>
        </div>
    """, unsafe_allow_html=True)
    menu = st.radio("MAIN MENU", ["⚡ 智能工作台", "📚 公共词书库", "👤 个人中心"], label_visibility="collapsed")
    st.markdown("---")
    st.info("📢 字幕文件无需转换，直接拖入即可。")

# 顶部导航
st.markdown("""
<div class="top-nav">
    <div style="font-weight:700; color:#334155;">Dashboard</div>
    <div style="font-size:12px; background:white; padding:4px 10px; border-radius:20px; border:1px solid #e2e8f0;">User: Free Plan</div>
</div>
""", unsafe_allow_html=True)

# === ⚡ 智能工作台 ===
if "工作台" in menu:
    
    # 1. 资源导航 (完整使用你提供的内容)
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

    # 2. 主操作区 (左右分栏，原生卡片)
    if 'result_words' not in st.session_state: st.session_state.result_words = []
    
    col_conf, col_input = st.columns([1, 2], gap="medium")

    # 左侧：配置卡片
    with col_conf:
        with st.container(border=True):
            st.markdown("##### 🛠️ 提取配置")
            nlp_mode = st.selectbox("AI 引擎", ["nltk (快速)", "spacy (精准)"])
            sort_order = st.selectbox("排序", ["按词频排序", "A-Z 排序", "随机打乱"])
            min_len = st.slider("最短词长", 2, 15, 3)
            
            st.divider()
            st.markdown("##### 🛡️ 熟词屏蔽")
            selected_presets = st.multiselect("预置库", PRESET_WORDLISTS.keys(), default=[])
            filter_file = st.file_uploader("自定义屏蔽表 (.txt)", type=['txt'])

    # 右侧：输入卡片
    with col_input:
        with st.container(border=True):
            st.markdown("""
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <b>📄 输入源 (Input Source)</b>
                <span style="font-size:12px; color:#64748b; background:#f1f5f9; padding:2px 6px; border-radius:4px;">支持 .txt .srt .docx .pdf</span>
            </div>
            """, unsafe_allow_html=True)
            
            tab_txt, tab_file = st.tabs(["✍️ 粘贴文本", "📂 上传文件"])
            
            with tab_txt:
                input_text = st.text_area("粘贴区域", height=250, placeholder="在此直接粘贴文章、字幕文本...", label_visibility="collapsed")
            with tab_file:
                uploaded_files = st.file_uploader("拖拽区域", type=['txt','srt','ass','docx','pdf'], accept_multiple_files=True, label_visibility="collapsed")

            st.markdown("<br>", unsafe_allow_html=True)
            start_btn = st.button("🚀 开始智能提取", type="primary")

    # 逻辑处理
    if start_btn:
        full_text = input_text
        if uploaded_files:
            for f in uploaded_files:
                full_text += "\n" + extract_text_from_bytes(f, f.name)
        
        if not full_text.strip():
            st.warning("⚠️ 请先输入文本或上传文件")
        else:
            filter_set = set()
            for p in selected_presets:
                if os.path.exists(PRESET_WORDLISTS[p]):
                    with open(PRESET_WORDLISTS[p], 'r', encoding='utf-8') as f: filter_set.update(f.read().splitlines())
            if filter_file:
                filter_set.update(filter_file.getvalue().decode('utf-8', errors='ignore').splitlines())
            
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            words = process_words(full_text, mode_key, min_len, filter_set)

            if sort_order == "A-Z 排序": words.sort(key=lambda x: x[0])
            elif sort_order == "随机打乱": random.shuffle(words)
            # "按词频排序" 保持 process_words 返回的默认顺序

            st.session_state.result_words = words
            st.rerun()

    # 3. 结果展示
    if st.session_state.result_words:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            words = st.session_state.result_words
            # 展示格式：word (count)
            display_str = "\n".join([f"{w} ({c})" for w, c in words])
            # 纯单词列表，用于复制/导出/发布
            plain_str = "\n".join([w for w, _ in words])

            st.markdown(f"### 🎉 提取结果 (共 {len(words)} 词)")
            st.text_area("Result", value=display_str, height=200, label_visibility="collapsed")

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1: copy_btn(plain_str)
            with c2: st.download_button("📦 下载 (.txt)", plain_str, "vocab.txt", "text/plain", use_container_width=True)
            with c3:
                with st.popover("☁️ 发布到社区库", use_container_width=True):
                    with st.form("pub_form"):
                        name = st.text_input("文件名 (英文, e.g. friends_s1.txt)", f"list_{int(time.time())}.txt")
                        title = st.text_input("标题")
                        desc = st.text_area("描述")
                        if st.form_submit_button("发布"):
                            if name.endswith(".txt"): save_to_github_library(name, plain_str, title, desc)
                            else: st.error("文件名需以 .txt 结尾")

# === 📚 公共词书库 ===
elif "词书库" in menu:
    # 顶部工具栏卡片
    with st.container(border=True):
        q = st.text_input("搜索", placeholder="🔍 搜索书名...", label_visibility="collapsed")

    # 动态读取 Library (修复点：从本地目录读取)
    try:
        with open(os.path.join(LIBRARY_DIR, "info.json"), "r", encoding="utf-8") as f: book_info = json.load(f)
    except: book_info = {}
    
    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    visible = [f for f in files if q.lower() in f.lower() or q.lower() in book_info.get(f, {}).get("title", "").lower()]
    
    if not visible:
        st.info("📭 暂无数据，请先去工作台发布词书。")
    else:
        st.markdown("<br>", unsafe_allow_html=True)
        cols = st.columns(4)
        colors = ["#fef3c7", "#d1fae5", "#dbeafe", "#fee2e2", "#f3e8ff"]
        txt_colors = ["#92400e", "#065f46", "#1e40af", "#991b1b", "#6b21a8"]
        
        for i, f in enumerate(visible):
            meta = book_info.get(f, {})
            title = meta.get("title", f)
            desc = meta.get("desc", "无描述")
            idx = i % 5
            
            with cols[i % 4]:
                st.markdown(f"""
                <div class="book-3d" style="background-color:{colors[idx]}; color:{txt_colors[idx]};">
                    <h4 style="margin:0; font-size:16px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; width:100%;">{title}</h4>
                    <p style="font-size:12px; opacity:0.8; margin-top:5px; height:36px; overflow:hidden;">{desc[:40]}...</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("操作"):
                    try:
                        with open(os.path.join(LIBRARY_DIR, f), 'r', encoding='utf-8') as _f: content = _f.read()
                        st.caption(f"文件名: {f}")
                        st.download_button("⬇️ 下载", content, f)
                        copy_btn(content)
                    except: st.error("文件读取失败")

else:
    st.info("🚧 个人中心开发中...")
