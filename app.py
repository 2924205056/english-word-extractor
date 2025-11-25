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

# ------------------ 页面配置 ------------------
st.set_page_config(
    page_title="万能词书平台 | Vocabulary Builder", 
    page_icon="📘", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义简单的 CSS 优化视觉体验
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ 缓存资源加载 ------------------
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

# ------------------ 核心逻辑保持不变 ------------------
def save_to_github_library(filename, content, title, desc):
    """将生成的词书上传到 GitHub 仓库"""
    try:
        # 安全检查：防止未配置 secrets 报错
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("未配置 GITHUB_TOKEN，无法连接云端。")
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
            st.toast(f"文件 {filename} 已更新！", icon="✅")
        except:
            repo.create_file(library_path, f"Create {filename}", content)
            st.toast(f"文件 {filename} 已创建！", icon="✅")

        try:
            info_contents = repo.get_contents(info_path)
            info_data = json.loads(info_contents.decoded_content.decode("utf-8"))
        except:
            info_data = {}
            info_contents = None

        info_data[filename] = {
            "title": title,
            "desc": desc,
            "timestamp": time.time() # 增加时间戳
        }
        
        new_info_str = json.dumps(info_data, indent=2, ensure_ascii=False)
        if info_contents:
            repo.update_file(info_path, "Update info.json", new_info_str, info_contents.sha)
        else:
            repo.create_file(info_path, "Create info.json", new_info_str)
            
        st.balloons()
        st.success(f"🎉 成功保存到云端！请刷新页面查看“公共词书库”。")
        
    except Exception as e:
        st.error(f"上传失败: {e}")
        st.info("请检查 Streamlit Secrets 配置。")

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
            st.error("不支持 .doc 格式，请另存为 .docx 后上传")
            return ""
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception as e: return ""
    
    if ext in ['srt', 'vtt', 'ass']:
        clean_text = re.sub(r"<.*?>", "", text) # 基础清洗
        # 针对 srt 时间轴的额外简单清洗（可选）
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

# ------------------ UI 逻辑 ------------------

# 侧边栏导航
with st.sidebar:
    st.title("📘 万能词书平台")
    st.caption("提取 · 整理 · 分享")
    st.divider()
    page = st.radio("功能导航:", ["🛠️ 制作生词本", "📚 公共词书库"], index=0)
    st.divider()
    st.markdown("💡 **Tips:**\n支持字幕文件、文档，自动提取生词并还原词形。")

if page == "🛠️ 制作生词本":
    # 顶部 Hero 区域
    st.title("🛠️ 英语生词提取器")
    st.markdown("""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
        上传您的 <b>字幕文件</b> (.srt, .vtt) 或 <b>文档</b> (.docx, .txt)，
        AI 引擎将自动为您提取高频生词，过滤简单词汇。
    </div>
    """, unsafe_allow_html=True)

    # 布局：左侧设置，右侧主操作
    col_settings, col_main = st.columns([1, 3])

    with col_settings:
        st.subheader("⚙️ 提取设置")
        
        with st.expander("🧠 处理引擎", expanded=True):
            nlp_mode = st.selectbox("选择引擎", ["nltk (快速)", "spacy (精准)"], help="Spacy 还原词形更准，但速度较慢")
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
        
        with st.expander("📏 过滤规则", expanded=True):
            min_len = st.number_input("单词最短长度", value=3, min_value=1)
            filter_file = st.file_uploader("上传熟词表 (txt)", type=['txt'], help="上传包含您已认识单词的txt文件，一行一个")
        
        with st.expander("📂 输出格式"):
            chunk_size = st.number_input("单文件词数限制", value=5000)
            sort_order = st.radio("排序方式", ["按文本出现顺序", "A-Z 排序", "随机打乱"])

        filter_set = set()
        if filter_file:
            c = filter_file.getvalue().decode("utf-8", errors='ignore')
            filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
            st.caption(f"✅ 已加载 {len(filter_set)} 个熟词")

    with col_main:
        st.subheader("📂 文件上传")
        uploaded_files = st.file_uploader(
            "拖拽文件到此处", 
            type=['txt','srt','ass','vtt','docx'], 
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

        if 'result_words' not in st.session_state:
            st.session_state.result_words = []

        # 操作按钮区域
        if uploaded_files:
            if st.button("🚀 开始智能提取", type="primary", use_container_width=True):
                all_raw_text = []
                for file in uploaded_files:
                    text = extract_text_from_bytes(file, file.name)
                    all_raw_text.append(text)
                
                full_text = "\n".join(all_raw_text)
                if full_text.strip():
                    with st.status("正在分析文本...", expanded=True) as status:
                        st.write("正在读取文件内容...")
                        time.sleep(0.5)
                        st.write(f"正在使用 {mode_key.upper()} 引擎提取单词...")
                        words = process_words(full_text, mode_key, min_len, filter_set)
                        
                        st.write("正在应用排序规则...")
                        if sort_order == "A-Z 排序":
                            words.sort()
                        elif sort_order == "随机打乱":
                            random.shuffle(words)
                        
                        st.session_state.result_words = words
                        status.update(label="✅ 提取完成！", state="complete", expanded=False)
                else:
                    st.warning("⚠️ 未能从文件中提取到有效文本。")

    # 结果展示区域（全宽）
    if st.session_state.result_words:
        result_words = st.session_state.result_words
        st.divider()
        
        # 统计仪表盘
        m1, m2, m3 = st.columns(3)
        m1.metric("提取单词总数", len(result_words))
        m2.metric("来源文件数", len(uploaded_files) if uploaded_files else 0)
        m3.metric("过滤模式", "智能过滤 + 熟词表" if filter_set else "智能过滤")

        # 预览与导出 分栏
        st.subheader("👀 结果预览与导出")
        
        # 使用 Dataframe 展示，比纯文本更好看
        with st.expander("展开查看单词列表", expanded=False):
            # 简单的列表转DataFrame，方便展示
            st.dataframe(
                [{"Index": i+1, "Word": w} for i, w in enumerate(result_words)],
                use_container_width=True,
                height=300,
                hide_index=True
            )

        # 使用 Tabs 优化导出区域，节省空间
        tab1, tab2 = st.tabs(["📥 本地下载 (Download)", "☁️ 发布到云端 (Publish)"])
        
        with tab1:
            st.info("将单词表打包下载到本地。")
            zip_buffer = io.BytesIO()
            num_files = math.ceil(len(result_words) / chunk_size)
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(num_files):
                    s = i * chunk_size
                    e = min(s + chunk_size, len(result_words))
                    zf.writestr(f"word_list_{i+1}.txt", "\n".join(result_words[s:e]))
            
            col_dl_btn, _ = st.columns([1, 2])
            with col_dl_btn:
                st.download_button(
                    "📦 下载 ZIP 压缩包", 
                    zip_buffer.getvalue(), 
                    "vocabulary_words.zip", 
                    "application/zip",
                    type="primary"
                )

        with tab2:
            st.success("将您的生词本分享给所有人。")
            with st.form("upload_form"):
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    save_name = st.text_input("文件名 (必须包含 .txt)", value=f"vocab_{int(time.time())}.txt")
                    save_title = st.text_input("词书标题", value="我的专属生词本")
                with f_col2:
                    save_desc = st.text_area("词书描述 / 来源说明", value="提取自...", height=103)
                
                submitted = st.form_submit_button("🚀 确认上传并发布")
                
                if submitted:
                    if not save_name.endswith(".txt"):
                        st.error("❌ 文件名必须以 .txt 结尾")
                    else:
                        content_str = "\n".join(result_words)
                        with st.spinner("正在连接 GitHub 仓库..."):
                            save_to_github_library(save_name, content_str, save_title, save_desc)

elif page == "📚 公共词书库":
    st.title("📚 公共词书库")
    st.markdown("这里存放了社区分享的精选生词本，您可以 **免费预览** 或 **下载**。")
    st.divider()
    
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    
    if not os.path.exists(LIBRARY_DIR):
        try:
            os.makedirs(LIBRARY_DIR)
        except:
            pass
    
    book_info = {}
    info_path = os.path.join(LIBRARY_DIR, INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f: book_info = json.load(f)
        except: pass

    try:
        files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    except FileNotFoundError:
        files = []
    
    if not files:
        st.container().warning("📭 暂无公共词书，快去“制作生词本”里上传您的第一本吧！")
    else:
        # 优化：使用 Grid 布局显示卡片，而不是简单的两列
        cols = st.columns(3) # 3列布局
        for i, filename in enumerate(files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f: file_content = f.read()
                word_count = len(file_content.splitlines())
                
                meta = book_info.get(filename, {})
                display_title = meta.get("title", filename)
                display_desc = meta.get("desc", "暂无描述")
                
                # 轮询放入 3 列中
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(f"📄 {display_title}")
                        st.markdown(f"**单词数:** `{word_count}`")
                        st.caption(display_desc)
                        
                        # 预览前几个词
                        preview_words = file_content.splitlines()[:5]
                        st.text("Preview: " + ", ".join(preview_words) + "...")
                        
                        st.download_button(
                            f"📥 下载", 
                            file_content, 
                            filename, 
                            "text/plain",
                            key=f"dl_{i}",
                            use_container_width=True
                        )
            except Exception as e:
                continue
