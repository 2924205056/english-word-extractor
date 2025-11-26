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

# --- 【修正】确保引入 copy 库 ---
import copy

import streamlit_authenticator as stauth

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

# ------------------ 0. 初始化：准备预置词库数据 ------------------
WORDLIST_DIR = "wordlists"
if not os.path.exists(WORDLIST_DIR):
    os.makedirs(WORDLIST_DIR)
    # 创建演示用文件 (请用真实文件替换)
    with open(os.path.join(WORDLIST_DIR, "primary.txt"), "w", encoding="utf-8") as f:
        f.write("a\nan\nthe\nis\nare\nam\nhello\ngood\nmorning\napple\nbanana\ncat\ndog\nbook\npen")
    with open(os.path.join(WORDLIST_DIR, "zhongkao.txt"), "w", encoding="utf-8") as f:
        f.write("ability\nabsent\naccept\naccording\nachieve\nactive\nactually\nadd\naddress\nadmit")
    with open(os.path.join(WORDLIST_DIR, "gaokao.txt"), "w", encoding="utf-8") as f:
        f.write("abandon\nability\nabnormal\naboard\nabolish\nabortion\nabrupt\nabsence\nabsolute\nabsorb")
    print(f"已在 {WORDLIST_DIR} 目录下创建演示词表文件。请替换为真实数据。")

PRESET_WORDLISTS = {
    "👶 小学核心词 ": os.path.join(WORDLIST_DIR, "primary.txt"),
    "👦 中考必备词 ": os.path.join(WORDLIST_DIR, "zhongkao.txt"),
    "👨‍🎓 高考3500词 ": os.path.join(WORDLIST_DIR, "gaokao.txt"),
}

# ------------------ 1. 页面配置 ------------------
st.set_page_config(
    page_title="VocabMaster Pro | 智能词书工坊",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# === 【身份验证逻辑开始】 ===
# ==============================================================================

# 1. 从 Streamlit Secrets 加载认证配置并创建副本
try:
    # 检查 keys 是否存在
    if "auth" not in st.secrets:
         st.error("Secrets 中未找到 'auth' 字段配置。请检查 Streamlit Cloud 设置。")
         st.stop()
    
    # --- 【核心修正点】 ---
    # 使用 copy.deepcopy() 创建 Secrets 的深拷贝。
    # 这样 authenticator 就可以修改 config 这个副本，而不会触发 Secrets 的只读错误。
    config = copy.deepcopy(st.secrets["auth"])

except Exception as e:
    st.error(f"加载认证配置失败: {e}")
    st.stop()

# 2. 初始化认证对象
# 此时传入的 config 是一个可修改的副本
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# 3. 在侧边栏创建登录框
name, authentication_status, username = authenticator.login('登录 VocabMaster', 'sidebar')

# 4. 根据登录状态决定显示什么
if authentication_status is False:
    st.sidebar.error('用户名或密码错误')
    st.stop()
elif authentication_status is None:
    st.sidebar.warning('请在上方输入账号密码登录。')
    st.title("🔒 欢迎来到 VocabMaster Pro")
    st.markdown("### 您的智能生词本专家")
    st.info("为了保护数据安全并提供个性化服务，请先在左侧侧边栏登录。")
    st.stop()

# ==============================================================================
# === 【身份验证逻辑结束】 ===
# === 只有当 authentication_status 为 True 时，代码才会继续往下走 ===
# ==============================================================================

# 登录成功！
elif authentication_status:
    with st.sidebar:
        st.write(f'👋 欢迎回来, **{name}**!')
        authenticator.logout('退出登录', 'sidebar')
        st.divider()

    # ------------------------------------------------------------------------------
    # 原有核心业务代码 (已缩进)
    # ------------------------------------------------------------------------------

    # 注入 CSS
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        h1, h2, h3, h4, h5 { color: #1e293b; font-family: 'Inter', sans-serif; font-weight: 700; letter-spacing: -0.025em; }
        p, div, span { color: #475569; line-height: 1.6; }
        section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f1f5f9; box-shadow: 4px 0 24px rgba(0,0,0,0.02); }
        [data-testid="stExpander"], [data-testid="stForm"], [data-testid="stContainer"] { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); transition: all 0.3s ease; }
        .streamlit-expanderHeader { background-color: transparent; color: #334155; font-weight: 600; }
        div.stButton > button { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; border-radius: 10px; padding: 0.6rem 1.2rem; font-weight: 600; font-size: 0.95rem; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); transition: transform 0.2s ease, box-shadow 0.2s ease; }
        div.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 8px 16px rgba(79, 70, 229, 0.4); color: white; }
        div.stButton > button[kind="secondary"] { background: white; color: #4f46e5; border: 1px solid #e2e8f0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        a[kind="primary"] { background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important; border: none !important; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important; border-radius: 10px !important; color: white !important; font-weight: 600 !important; text-decoration: none !important; display: flex; justify-content: center; align-items: center; padding: 0.6rem 1.2rem; transition: transform 0.2s ease !important; }
        a[kind="primary"]:hover { transform: translateY(-2px); }
        .stTextInput > div > div, .stSelectbox > div > div, .stNumberInput > div > div, .stMultiSelect > div > div { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; color: #334155; }
        .stTextInput > div > div:focus-within, .stMultiSelect > div > div:focus-within { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1); }
        .stMultiSelect [data-baseweb="tag"] { background-color: #e0e7ff; border: 1px solid #c7d2fe; color: #4f46e5; }
        .step-header { font-size: 1.25rem; font-weight: 700; color: #334155; margin-bottom: 16px; display: flex; align-items: center; padding-bottom: 8px; border-bottom: 2px solid #f1f5f9; }
        .info-box { background: rgba(239, 246, 255, 0.7); backdrop-filter: blur(10px); border: 1px solid #dbeafe; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 8px; color: #1e40af; font-size: 0.95em; margin-bottom: 20px; }
        .stCodeBlock { max-height: 220px !important; overflow-y: auto !important; border: 1px solid #cbd5e1; border-radius: 8px; background-color: #f1f5f9; font-family: 'JetBrains Mono', monospace; }
        [data-testid="stMetric"] { background-color: white; padding: 15px; border-radius: 12px; border: 1px solid #f1f5f9; box-shadow: 0 2px 4px rgba(0,0,0,0.02); text-align: center; }
        [data-testid="stMetricLabel"] { color: #64748b; font-size: 0.9rem; }
        [data-testid="stMetricValue"] { color: #4f46e5; font-size: 1.8rem; font-weight: 700; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] { background-color: white; border-radius: 8px 8px 0 0; border: 1px solid #e2e8f0; border-bottom: none; padding: 10px 20px; color: #64748b; }
        .stTabs [aria-selected="true"] { background-color: #f8fafc; color: #4f46e5; font-weight: 600; border-top: 2px solid #4f46e5; }
    </style>
    """, unsafe_allow_html=True)

    # 自定义复制按钮组件
    def render_copy_button(text_content, unique_key):
        safe_text = json.dumps(text_content)
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@600&display=swap');
            body {{ margin: 0; padding: 0; }}
            .copy-btn {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; border-radius: 10px; font-family: 'Inter', sans-serif; font-weight: 600; font-size: 15px; cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); letter-spacing: 0.02em; }}
            .copy-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(79, 70, 229, 0.4); filter: brightness(1.05); }}
            .copy-btn:active {{ transform: translateY(0); }}
            .icon {{ margin-right: 8px; font-size: 18px; }}
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
                    btn.style.background = "linear-gradient(135deg, #10b981 0%, #059669 100%)";
                    btn.style.boxShadow = "0 4px 12px rgba(16, 185, 129, 0.3)";
                    setTimeout(() => {{
                        btn.innerHTML = originalHTML;
                        btn.style.background = "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)";
                        btn.style.boxShadow = "0 4px 12px rgba(79, 70, 229, 0.3)";
                    }}, 2000);
                }} catch (err) {{}}
                document.body.removeChild(textArea);
            }}
            </script>
        </body>
        </html>
        """
        components.html(html_code, height=55)

    # 资源加载
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

    # 核心逻辑函数
    def save_to_github_library(filename, content, title, desc):
        try:
            if "GITHUB_TOKEN" not in st.secrets or "GITHUB_USERNAME" not in st.secrets or "GITHUB_REPO" not in st.secrets:
                st.error("🔒 系统未配置 GitHub Secrets，无法发布。")
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
                # 使用登录用户的名字作为作者
                "author": name 
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

    # UI 架构
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/dictionary.png", width=64)
        st.markdown("### VocabMaster")
        st.caption("v12.0 Pro Login Edition")
        st.markdown("---")
        menu = st.radio("选择功能", ["⚡ 制作生词本", "🌍 公共词书库"])
        st.markdown("---")
        st.info("**小贴士**\n使用 Spacy 引擎还原词形更准。")

    # === 制作生词本 ===
    if menu == "⚡ 制作生词本":
        st.title("⚡ 智能生词提取工坊")
        
        with st.expander("📖 新手指南 & 宝藏资源库 (点击展开)", expanded=False):
            t1, t2, t3, t4 = st.tabs(["💡 操作指引", "🎬 影视字幕", "📚 原著阅读", "🎧 听力素材"])
            with t1:
                st.markdown("""<div style="padding:5px;"><h5 style="margin-top:0">🚀 四步制作专属词书：</h5><ol><li><b>准备素材</b>：从右侧标签页下载 <code>.srt</code> 字幕或 <code>.txt</code> 电子书。</li><li><b>清洗设置</b>：在下方【设置提取规则】中，选择<b>“预置熟词库”</b>或上传自定义熟词表。</li><li><b>智能提取</b>：将文件拖入上传区，AI 自动完成去重、词形还原。</li><li><b>闭环学习</b>：点击生成的<b>“一键复制”</b>按钮，跳转扇贝网批量制卡。</li></ol></div>""", unsafe_allow_html=True)
            # ... (省略其他 tab 的内容以节省篇幅，它们都在) ...

        if 'result_words' not in st.session_state: st.session_state.result_words = []
        if 'source_files_count' not in st.session_state: st.session_state.source_files_count = 0
        
        c_config, c_upload = st.columns([1, 2], gap="large")
        
        with c_config:
            st.markdown('<div class="step-header">1️⃣ 设置提取规则</div>', unsafe_allow_html=True)
            with st.container(border=True):
                nlp_mode = st.selectbox("AI 引擎", ["nltk (快速)", "spacy (精准)"])
                mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
                min_len = st.number_input("单词最短长度", 3, 20, 3)
                st.markdown("---")
                sort_order = st.selectbox("🔀 单词排序", ["按文本出现顺序", "A-Z 排序", "随机打乱"])
                chunk_size = st.number_input("📥 文件拆分大小 (词/文件)", 5000, 50000, 5000, step=1000)
                
                st.markdown("---")
                st.markdown("##### 🛡️ 熟词屏蔽设置")
                selected_presets = st.multiselect("选择预置熟词库 (可多选, 叠加生效)", options=list(PRESET_WORDLISTS.keys()), default=[], help="选择你已经掌握的词汇等级，这些词将不会出现在最终结果中。")
                filter_file = st.file_uploader("上传自定义熟词表 (.txt)", type=['txt'], help="如果你有自己的专属词表，可以在这里上传，将与预置词库叠加。")
                
                filter_set = set()
                for preset_name in selected_presets:
                    file_path = PRESET_WORDLISTS[preset_name]
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                words_in_file = set(l.strip().lower() for l in f if l.strip())
                                filter_set.update(words_in_file)
                        except Exception as e:
                             st.warning(f"读取词库 {preset_name} 失败: {e}")
                    else:
                         st.warning(f"找不到词库文件: {file_path}")

                if filter_file:
                    c = filter_file.getvalue().decode("utf-8", errors='ignore')
                    custom_words = set(l.strip().lower() for l in c.splitlines() if l.strip())
                    filter_set.update(custom_words)
                    
                if filter_set:
                    st.caption(f"✅ 已启用屏蔽，共计 {len(filter_set)} 个熟词。")
                else:
                     st.caption("ℹ️ 未启用任何熟词屏蔽。")

        with c_upload:
            st.markdown('<div class="step-header">2️⃣ 上传与分析</div>', unsafe_allow_html=True)
            with st.container(border=True):
                uploaded_files = st.file_uploader("支持 .srt,.ass,.docx, .txt", type=['txt','srt','ass','docx'], accept_multiple_files=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if uploaded_files and st.button("🚀 开始提取", type="primary", use_container_width=True):
                    my_bar = st.progress(0, text="读取文件...")
                    all_text = []
                    for i, f in enumerate(uploaded_files):
                        all_text.append(extract_text_from_bytes(f, f.name))
                        my_bar.progress((i+1)/len(uploaded_files))
                    
                    full_text = "\n".join(all_text)
                    if full_text.strip():
                        my_bar.progress(100, text="AI 分析中 (可能需要一点时间)...")
                        words = process_words(full_text, mode_key, min_len, filter_set)
                        if sort_order == "A-Z 排序": words.sort()
                        elif sort_order == "随机打乱": random.shuffle(words)
                        st.session_state.result_words = words
                        st.session_state.source_files_count = len(uploaded_files)
                        my_bar.empty()
                        st.rerun()
                    else:
                        st.error("未提取到文本。")

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
                st.code(content_str, language="text")
                
            with col_act:
                st.markdown("##### 🚀 操作")
                st.markdown("""<a href="https://web.shanbay.com/wordsweb/#/books" target="_blank" kind="primary">🦁 导入扇贝 (Web)</a>""", unsafe_allow_html=True)
                st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
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
                        name_input = st.text_input("文件名(.txt)", value=f"v_{int(time.time())}.txt")
                        title_input = st.text_input("标题")
                        desc_input = st.text_area("简介")
                        if st.form_submit_button("提交"):
                            if name_input.endswith(".txt"): save_to_github_library(name_input, content_str, title_input, desc_input)

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
                            c1, c2 = st.columns(2)
                            with c1: st.markdown("""<a href="https://web.shanbay.com/wordsweb/#/books" target="_blank" kind="primary" style="font-size:0.8rem; padding:0.4rem;">🚀 导入</a>""", unsafe_allow_html=True)
                            with c2: st.download_button("⬇️ 下载", content, f, "text/plain", use_container_width=True)
                            with st.expander("👀 展开查看与复制"):
                                st.caption(desc)
                                render_copy_button(content, f"lib_copy_{i}")
                                st.code(content, language="text")
                except: continue
