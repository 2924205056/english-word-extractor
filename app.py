import streamlit as st
import io
import re
import zipfile
import math
import chardet
import os
import json
import random
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

# ------------------ 页面配置 ------------------
st.set_page_config(
    page_title="万能词书平台", 
    page_icon="📘", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 优化样式
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    .stTabs [aria-selected="true"] { background-color: #ffffff; border-top: 2px solid #ff4b4b; }
    .metric-card { background-color: #f9f9f9; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ------------------ 缓存资源加载 ------------------
@st.cache_resource
def download_nltk_resources():
    resources = ["punkt", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "wordnet", "omw-1.4", "stopwords"]
    for r in resources:
        try:
            nltk.data.find(f'tokenizers/{r}')
        except (LookupError, ValueError):
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
    try:
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
            "desc": desc
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
        st.warning("请检查 .streamlit/secrets.toml 配置是否正确。")

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
            st.error(f"不支持 .doc 格式 ({filename})，请转存为 .docx")
            return ""
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception as e: return ""
    
    if ext in ['srt', 'vtt', 'ass']:
        clean_text = re.sub(r"<.*?>", "", text)
        clean_text = re.sub(r"\{.*?\}", "", clean_text) # Remove ASS tags
        return clean_text
    return text

def process_words(all_text, mode, min_len, filter_set=None):
    TOKEN_RE = re.compile(r"[A-Za-z-]+")
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in TOKEN_RE.findall(all_text) if w]
    lemmatized = []
    
    # 模拟进度条需要外部传入 callback，这里简化处理
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
    st.title("📘 万能词书")
    page = st.radio("功能导航", ["🛠️ 制作生词本", "📚 公共词书库"], label_visibility="collapsed")
    st.divider()
    st.caption("Version 2.0 | Power by NLP")

if page == "🛠️ 制作生词本":
    st.markdown("## 🛠️ 英语生词提取器")
    st.info("💡 上传字幕或文档，系统将自动去除简单词、还原词形，生成你的专属单词书。")

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("1. 提取设置")
        with st.expander("⚙️ 高级配置 (点击展开)", expanded=True):
            nlp_mode = st.selectbox("NLP 引擎", ["nltk (速度快)", "spacy (精度高)"], help="Spacy 对词性还原更准确，但速度稍慢。")
            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
            min_len = st.slider("最短单词长度", 2, 10, 3)
            
            st.divider()
            st.write("🚫 **过滤词表** (可选)")
            filter_file = st.file_uploader("上传熟词表 (txt)", type=['txt'], label_visibility="collapsed")
            filter_set = set()
            if filter_file:
                c = filter_file.getvalue().decode("utf-8", errors='ignore')
                filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
                st.success(f"✅ 已加载 {len(filter_set)} 个过滤词")

    with col2:
        st.subheader("2. 上传与处理")
        uploaded_files = st.file_uploader("拖拽或点击上传文件 (支持 .srt, .docx, .txt 等)", type=['txt','srt','ass','vtt','docx'], accept_multiple_files=True)
        
        process_btn = st.button("🚀 开始智能提取", type="primary", use_container_width=True, disabled=not uploaded_files)

    if 'result_words' not in st.session_state:
        st.session_state.result_words = []

    if process_btn and uploaded_files:
        all_raw_text = []
        
        # 使用 status 组件显示详细状态
        with st.status("正在处理文件中...", expanded=True) as status:
            st.write("📖 读取文件内容...")
            for file in uploaded_files:
                text = extract_text_from_bytes(file, file.name)
                all_raw_text.append(text)
            
            full_text = "\n".join(all_raw_text)
            
            if full_text.strip():
                st.write(f"🧠 调用 {mode_key.upper()} 引擎进行自然语言分析...")
                words = process_words(full_text, mode_key, min_len, filter_set)
                st.session_state.result_words = words # 默认暂不排序，保留提取顺序
                status.update(label="✅ 提取完成！", state="complete", expanded=False)
            else:
                status.update(label="❌ 未提取到文本", state="error")
                st.warning("请检查文件内容是否为空。")

    # 结果展示区
    if st.session_state.result_words:
        st.divider()
        result_words = st.session_state.result_words
        
        # 顶部数据指标
        m1, m2, m3 = st.columns(3)
        m1.metric("提取单词总数", len(result_words))
        m2.metric("过滤词数", len(filter_set) if filter_set else 0)
        m3.metric("预估掌握用时", f"{math.ceil(len(result_words)/30)} 天", help="按每天背30个单词计算")
        
        # 操作区域 Tab 分页
        tab1, tab2, tab3 = st.tabs(["👀 列表预览", "📥 本地导出", "☁️ 发布到云端"])
        
        with tab1:
            # 转换为 DataFrame 方便展示
            import pandas as pd
            df_words = pd.DataFrame(result_words, columns=["Words"])
            st.dataframe(df_words, use_container_width=True, height=300)

        with tab2:
            st.subheader("导出选项")
            c1, c2 = st.columns(2)
            with c1:
                sort_order = st.radio("排序方式", ["按文本顺序", "A-Z 排序", "随机打乱 (推荐复习)"])
            with c2:
                chunk_size = st.number_input("单文件单词上限", value=5000, step=1000)
            
            # 临时应用排序
            export_words = result_words.copy()
            if sort_order == "A-Z 排序":
                export_words.sort()
            elif sort_order == "随机打乱 (推荐复习)":
                random.shuffle(export_words)

            zip_buffer = io.BytesIO()
            num_files = math.ceil(len(export_words) / chunk_size)
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(num_files):
                    s = i * chunk_size
                    e = min(s + chunk_size, len(export_words))
                    zf.writestr(f"word_list_{i+1}.txt", "\n".join(export_words[s:e]))
            
            st.download_button(
                label=f"📥 下载生词本 (ZIP, 共{num_files}个文件)", 
                data=zip_buffer.getvalue(), 
                file_name="my_vocab_book.zip", 
                mime="application/zip",
                type="primary"
            )

        with tab3:
            col_cloud_form, col_cloud_tips = st.columns([2, 1])
            with col_cloud_form:
                with st.form("upload_form"):
                    st.write("填写词书信息")
                    save_name = st.text_input("文件名 (e.g. harry_potter.txt)", value="new_book.txt")
                    save_title = st.text_input("标题", value="我的生词本")
                    save_desc = st.text_area("简介", value="提取自...")
                    submitted = st.form_submit_button("🚀 确认发布")
                    
                    if submitted:
                        if not save_name.endswith(".txt"):
                            st.error("文件名必须以 .txt 结尾")
                        else:
                            # 默认发布前按 A-Z 排序，比较整齐
                            final_content = sorted(list(set(result_words)))
                            content_str = "\n".join(final_content)
                            with st.spinner("正在连接 GitHub..."):
                                save_to_github_library(save_name, content_str, save_title, save_desc)
            with col_cloud_tips:
                st.info("ℹ️ 说明：\n发布后，该词书将出现在“公共词书库”中，所有人均可下载。\n请确保内容不包含敏感信息。")

elif page == "📚 公共词书库":
    st.markdown("## 📚 公共词书库")
    st.caption("这里汇聚了大家分享的优质生词本，点击即可免费下载。")
    
    col_search, _ = st.columns([1, 2])
    search_query = col_search.text_input("🔍 搜索词书", placeholder="输入标题或描述关键字...").lower()
    
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
    
    book_info = {}
    info_path = os.path.join(LIBRARY_DIR, INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f: book_info = json.load(f)
        except: pass

    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    
    # 过滤搜索
    filtered_files = []
    for f in files:
        meta = book_info.get(f, {})
        title = meta.get("title", f).lower()
        desc = meta.get("desc", "").lower()
        if search_query in title or search_query in desc or search_query in f.lower():
            filtered_files.append(f)

    if not filtered_files:
        st.warning("📭 暂无相关词书，快去“制作生词本”里上传一本吧！")
    else:
        # 使用 Grid 布局 (每行3个)
        cols = st.columns(3)
        for i, filename in enumerate(filtered_files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f: file_content = f.read()
            word_count = len(file_content.splitlines())
            
            meta = book_info.get(filename, {})
            display_title = meta.get("title", filename)
            display_desc = meta.get("desc", "暂无描述")
            
            # 使用 Container 模拟卡片样式
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(f"📄 {display_title}")
                    st.caption(f"文件名: {filename}")
                    st.text(f"📊 单词量: {word_count}")
                    
                    # 限制描述文字高度，防止卡片参差不齐
                    if len(display_desc) > 50:
                        short_desc = display_desc[:50] + "..."
                        st.markdown(f"<div style='height:45px; overflow:hidden; color:gray; font-size:0.9em'>{short_desc}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='height:45px; color:gray; font-size:0.9em'>{display_desc}</div>", unsafe_allow_html=True)
                    
                    st.download_button(
                        f"📥 下载", 
                        file_content, 
                        filename, 
                        "text/plain", 
                        key=f"dl_{i}",
                        use_container_width=True
                    )
