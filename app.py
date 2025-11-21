import streamlit as st
import io
import re
import zipfile
import math
import chardet
import os
import json
from github import Github # 新增：用于操作 GitHub

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
st.set_page_config(page_title="万能词书平台", page_icon="📘", layout="wide")

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

# ------------------ GitHub 上传函数 (核心新功能) ------------------
def save_to_github_library(filename, content, title, desc):
    """将生成的词书上传到 GitHub 仓库"""
    try:
        # 1. 获取 Secrets 里的配置
        token = st.secrets["GITHUB_TOKEN"]
        username = st.secrets["GITHUB_USERNAME"]
        repo_name = st.secrets["GITHUB_REPO"]
        
        # 2. 连接 GitHub
        g = Github(token)
        repo = g.get_repo(f"{username}/{repo_name}")
        
        library_path = f"library/{filename}"
        info_path = "library/info.json"
        
        # 3. 创建或更新词书文件 (.txt)
        try:
            contents = repo.get_contents(library_path)
            # 如果文件存在，更新它
            repo.update_file(library_path, f"Update {filename}", content, contents.sha)
            st.toast(f"文件 {filename} 已更新！", icon="✅")
        except:
            # 如果文件不存在，创建它
            repo.create_file(library_path, f"Create {filename}", content)
            st.toast(f"文件 {filename} 已创建！", icon="✅")

        # 4. 更新 info.json 描述文件
        try:
            info_contents = repo.get_contents(info_path)
            # 读取旧的 info.json
            info_data = json.loads(info_contents.decoded_content.decode("utf-8"))
        except:
            # 如果 info.json 不存在，就新建一个空的
            info_data = {}
            info_contents = None

        # 更新数据
        info_data[filename] = {
            "title": title,
            "desc": desc
        }
        
        # 写回 GitHub
        new_info_str = json.dumps(info_data, indent=2, ensure_ascii=False)
        if info_contents:
            repo.update_file(info_path, "Update info.json", new_info_str, info_contents.sha)
        else:
            repo.create_file(info_path, "Create info.json", new_info_str)
            
        st.success(f"🎉 成功保存到云端！请刷新页面查看“公共词书库”。")
        
    except Exception as e:
        st.error(f"上传失败: {e}")
        st.error("请检查 Streamlit Secrets 配置是否正确 (GITHUB_TOKEN 等)。")

# ------------------ 文本处理逻辑 ------------------
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
            st.error("不支持 .doc，请转存为 .docx")
            return ""
        else:
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception as e: return ""
    
    if ext in ['srt', 'vtt', 'ass']:
        clean_text = re.sub(r"<.*?>", "", text)
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

st.sidebar.title("功能导航")
page = st.sidebar.radio("选择模式:", ["🛠️ 制作生词本", "📚 公共词书库"])

if page == "🛠️ 制作生词本":
    st.title("🛠️ 英语生词提取器")

    with st.sidebar:
        st.divider()
        nlp_mode = st.selectbox("引擎", ["nltk (快)", "spacy (准)"])
        mode_key = "spacy" if "spacy" in nlp_mode else "nltk"
        min_len = st.number_input("最短词长", value=3)
        filter_file = st.file_uploader("过滤词表", type=['txt'])
        filter_set = set()
        if filter_file:
            c = filter_file.getvalue().decode("utf-8", errors='ignore')
            filter_set = set(l.strip().lower() for l in c.splitlines() if l.strip())
            st.success(f"已加载 {len(filter_set)} 个过滤词")

    uploaded_files = st.file_uploader("上传文件", type=['txt','srt','ass','vtt','docx'], accept_multiple_files=True)

    # 使用 session_state 来保存处理结果，防止填写表单时刷新消失
    if 'result_words' not in st.session_state:
        st.session_state.result_words = []

    if uploaded_files and st.button("🚀 开始提取", type="primary"):
        all_raw_text = []
        for file in uploaded_files:
            text = extract_text_from_bytes(file, file.name)
            all_raw_text.append(text)
        
        full_text = "\n".join(all_raw_text)
        if full_text.strip():
            with st.spinner("分析中..."):
                st.session_state.result_words = process_words(full_text, mode_key, min_len, filter_set)
            st.success(f"提取成功！共 {len(st.session_state.result_words)} 个单词。")

    # 如果有结果，显示保存选项
    if st.session_state.result_words:
        result_words = st.session_state.result_words
        
        # 预览
        with st.expander("👀 预览结果", expanded=False):
            st.write(", ".join(result_words[:100]))

        st.divider()
        col_local, col_cloud = st.columns(2)
        
        # 本地下载
        with col_local:
            st.subheader("📥 仅下载")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("word_list.txt", "\n".join(result_words))
            st.download_button("下载 TXT 文件", zip_buffer.getvalue(), "words.zip", "application/zip")

        # 云端保存
        with col_cloud:
            st.subheader("☁️ 保存到公共库")
            with st.form("upload_form"):
                save_name = st.text_input("文件名 (必须以 .txt 结尾)", value="my_new_book.txt")
                save_title = st.text_input("词书标题", value="我的生词本")
                save_desc = st.text_area("词书描述", value="这是一本关于...")
                submitted = st.form_submit_button("确认上传并发布")
                
                if submitted:
                    if not save_name.endswith(".txt"):
                        st.error("文件名必须包含 .txt")
                    else:
                        content_str = "\n".join(result_words)
                        with st.spinner("正在连接 GitHub 上传中..."):
                            save_to_github_library(save_name, content_str, save_title, save_desc)

elif page == "📚 公共词书库":
    st.title("📚 公共词书库")
    
    LIBRARY_DIR = "library"
    INFO_FILE = "info.json"
    
    # 注意：云端运行时，library 文件夹是 GitHub 上的，但 streamlt 会 clone 下来
    # 我们优先读取本地 clone 下来的文件
    
    if not os.path.exists(LIBRARY_DIR):
        os.makedirs(LIBRARY_DIR)
    
    book_info = {}
    info_path = os.path.join(LIBRARY_DIR, INFO_FILE)
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f: book_info = json.load(f)
        except: pass

    files = [f for f in os.listdir(LIBRARY_DIR) if f.endswith(".txt")]
    
    if not files:
        st.warning("📭 暂无词书，快去“制作生词本”里上传一本吧！")
    else:
        col1, col2 = st.columns(2)
        for i, filename in enumerate(files):
            file_path = os.path.join(LIBRARY_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f: file_content = f.read()
            word_count = len(file_content.splitlines())
            
            meta = book_info.get(filename, {})
            display_title = meta.get("title", filename)
            display_desc = meta.get("desc", "暂无描述")
            
            with (col1 if i % 2 == 0 else col2):
                with st.container(border=True):
                    st.subheader(f"📄 {display_title}")
                    if display_desc != "暂无描述": st.info(display_desc)
                    else: st.caption("无详细描述")
                    st.caption(f"📚 单词数: **{word_count}**")
                    st.download_button(f"📥 下载 {filename}", file_content, filename, "text/plain")
