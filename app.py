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

# ------------------ 缓存资源加载 (核心修复部分) ------------------
@st.cache_resource
def download_nltk_resources():
    """静默下载 NLTK 资源"""
    # 这里的列表加上了 'averaged_perceptron_tagger_eng' 以修复云端报错
    resources = [
        "punkt", 
        "averaged_perceptron_tagger", 
        "averaged_perceptron_tagger_eng", 
        "wordnet", 
        "omw-1.4", 
        "stopwords"
    ]
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
            # 尝试加载小模型
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
    elif ext ==
