import streamlit as st
import io
import re
import zipfile
import math
import chardet

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
st.set_page_config(page_title="单词提取器 Web版", page_icon="📘", layout="wide")

# ------------------ 缓存资源加载 (避免重复加载) ------------------
@st.cache_resource
def download_nltk_resources():
    """静默下载 NLTK 资源"""
    resources = ["punkt", "averaged_perceptron_tagger", "wordnet", "omw-1.4", "stopwords"]
    for r in resources:
        try:
            nltk.data.find(f'tokenizers/{r}')
        except LookupError:
            nltk.download(r, quiet=True)
        except ValueError:
            # 部分资源路径不同，简单的 try-catch 处理
            nltk.download(r, quiet=True)

@st.cache_resource
def load_spacy_model():
    if _HAS_SPACY:
        try:
            # 尝试加载小模型，需提前 python -m spacy download en_core_web_sm
            return spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            return None
    return None

# 初始化资源
download_nltk_resources()
nlp_spacy = load_spacy_model()

# ------------------ 核心工具函数 ------------------

def extract_text_from_bytes(file_obj, filename):
    """从内存文件对象中提取文本"""
    ext = filename.split('.')[-1].lower()
    text = ""
    
    try:
        if ext == 'docx':
            doc = Document(file_obj)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)
        else:
            # 二进制读取并检测编码
            raw = file_obj.read()
            enc = chardet.detect(raw).get('encoding') or 'utf-8'
            text = raw.decode(enc, errors='ignore')
    except Exception as e:
        st.warning(f"⚠️ 读取 {filename} 失败: {e}")
        return ""

    # 针对字幕格式的清洗
    if ext == 'srt':
        return extract_english_from_srt(text)
    elif ext == 'ass':
        return extract_english_from_ass(text)
    elif ext == 'vtt':
        return extract_english_from_vtt(text)
    else:
        return text

def extract_english_from_srt(text):
    lines = []
    SRT_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[,.]\d{3}")
    for ln in text.splitlines():
        s = ln.strip()
        if not s: continue
        if s.isdigit() or SRT_TIME_RE.match(s): continue
        s = re.sub(r"<.*?>", "", s)
        s = re.sub(r"\[.*?\]", "", s)
        parts = re.findall(r"[A-Za-z0-9'\",.?!:;()\- ]+", s)
        if parts: lines.append("".join(parts).strip())
    return " ".join(lines)

def extract_english_from_ass(text):
    lines = []
    for ln in text.splitlines():
        if ln.startswith("Dialogue:"):
            parts = ln.split(",", 9)
            if len(parts) >= 10:
                t = re.sub(r"\{.*?\}", "", parts[-1])
                t = re.sub(r"<.*?>", "", t)
                parts2 = re.findall(r"[A-Za-z0-9'\",.?!:;()\- ]+", t)
                if parts2: lines.append("".join(parts2).strip())
    return " ".join(lines)

def extract_english_from_vtt(text):
    lines = []
    VTT_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}")
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("WEBVTT") or VTT_TIME_RE.match(s): continue
        s = re.sub(r"<.*?>", "", s)
        parts = re.findall(r"[A-Za-z0-9'\",.?!:;()\- ]+", s)
        if parts: lines.append("".join(parts).strip())
    return " ".join(lines)

def get_wordnet_pos(tag):
    if tag.startswith('J'): return wordnet.ADJ
    if tag.startswith('V'): return wordnet.VERB
    if tag.startswith('N'): return wordnet.NOUN
    if tag.startswith('R'): return wordnet.ADV
    return None

def process_words(all_text, mode, min_len, filter_set=None):
    """处理核心逻辑：分词 -> 还原 -> 过滤"""
    TOKEN_RE = re.compile(r"[A-Za-z-]+")
    raw_tokens = TOKEN_RE.findall(all_text)
    cleaned = [re.sub(r'[^a-z]', '', w.lower()) for w in raw_tokens]
    cleaned = [w for w in cleaned if w]

    lemmatized = []
    
    # 进度条容器
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 1. 词形还原
    if mode == "spacy" and nlp_spacy is not None:
        status_text.text("正在使用 spaCy 进行词形还原 (速度较慢，请耐心)...")
        # spaCy 处理限制长度以免内存溢出，分块处理
        chunk_size = 50000
        chunks = [cleaned[i:i + chunk_size] for i in range(0, len(cleaned), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            doc = nlp_spacy(" ".join(chunk))
            for token in doc:
                lw = token.lemma_.lower()
                if lw.isalpha() and wordnet.synsets(lw):
                    lemmatized.append(lw)
            progress_bar.progress((i + 1) / len(chunks))
            
    else:
        status_text.text("正在使用 NLTK 进行词形还原...")
        lemmatizer = WordNetLemmatizer()
        # NLTK 也可以分块显示进度
        tagged = pos_tag(cleaned)
        total = len(tagged)
        for i, (w, tag) in enumerate(tagged):
            wn = get_wordnet_pos(tag)
            lw = lemmatizer.lemmatize(w, wn) if wn else lemmatizer.lemmatize(w)
            # 简单的 WordNet 校验
            if wordnet.synsets(lw):
                lemmatized.append(lw)
            if i % 5000 == 0:
                progress_bar.progress(min(i / total, 1.0))
        progress_bar.progress(1.0)

    status_text.text("正在去重和过滤...")
    
    # 2. 去重、长度过滤、停用词过滤、自定义过滤
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
            
    status_text.empty()
    progress_bar.empty()
    
    return final_words

# ------------------ UI 布局 ------------------

st.title("📘 英语生词本生成器 (Word Extractor)")
st.markdown("""
上传字幕文件 (`.srt`, `.ass`, `.vtt`) 或文档 (`.docx`, `.txt`)，
系统将自动提取单词、还原词形、去除简单词，生成单词列表。
""")

with st.sidebar:
    st.header("⚙️ 设置")
    
    nlp_mode = st.selectbox(
        "NLP 引擎", 
        ["nltk (快速)", "spacy (精准, 需安装模型)"], 
        index=0
    )
    mode_key = "spacy" if "spacy" in nlp_mode else "nltk"

    st.divider()
    
    min_len = st.number_input("最小单词长度", min_value=1, value=3)
    chunk_size = st.number_input("输出切分 (每份单词数)", min_value=100, value=5000)
    
    sort_order = st.radio("排序方式", ["按文本出现顺序", "A-Z 排序", "随机打乱"])
    
    st.divider()
    
    filter_file = st.file_uploader("上传过滤词表 (如: 高考/四六级词库.txt)", type=['txt'])
    filter_set = set()
    if filter_file:
        content = filter_file.getvalue().decode("utf-8", errors='ignore')
        filter_set = set(line.strip().lower() for line in content.splitlines() if line.strip())
        st.success(f"已加载 {len(filter_set)} 个过滤词")

# 主区域
uploaded_files = st.file_uploader(
    "拖拽文件到此处 (支持批量)", 
    type=['txt', 'srt', 'ass', 'vtt', 'docx'], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("🚀 开始提取", type="primary"):
        all_raw_text = []
        
        # 1. 读取文件
        read_bar = st.progress(0)
        for i, file in enumerate(uploaded_files):
            text = extract_text_from_bytes(file, file.name)
            all_raw_text.append(text)
            read_bar.progress((i + 1) / len(uploaded_files))
        read_bar.empty()
        
        full_text = "\n".join(all_raw_text)
        st.info(f"已读取原始文本，约 {len(full_text)} 字符，开始处理...")
        
        # 2. NLP 处理
        result_words = process_words(full_text, mode_key, min_len, filter_set)
        
        # 3. 排序
        if sort_order == "A-Z 排序":
            result_words.sort()
        elif sort_order == "随机打乱":
            import random
            random.shuffle(result_words)
            
        # 4. 结果展示与打包
        st.success(f"🎉 处理完成！共提取到 **{len(result_words)}** 个有效生词。")
        
        # 预览
        with st.expander("👀 预览前 100 个单词"):
            st.write(", ".join(result_words[:100]))
            
        # 5. 生成下载文件 (Zip)
        if result_words:
            zip_buffer = io.BytesIO()
            num_files = math.ceil(len(result_words) / chunk_size)
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in range(num_files):
                    start = i * chunk_size
                    end = min(start + chunk_size, len(result_words))
                    chunk_data = "\n".join(result_words[start:end])
                    fname = f"word_list_{i+1}.txt"
                    zf.writestr(fname, chunk_data)
            
            st.download_button(
                label="📥 下载单词本 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="extracted_words.zip",
                mime="application/zip"
            )
        else:
            st.warning("未提取到任何单词，请检查输入文件。")
