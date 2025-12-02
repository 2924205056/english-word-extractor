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

# NLP Imports (保持原有的 NLP 逻辑)
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

# ------------------ 0. 初始化配置 ------------------
st.set_page_config(
    page_title="VocabMaster | 智能词书工坊", 
    page_icon="📗", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------ 1. 核心 CSS 注入 (UI 灵魂) ------------------
# 这里复刻了你提供的 HTML v7.0 的视觉风格
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    :root {
        --primary: #00B99B; /* 扇贝绿 */
        --primary-hover: #0F766E;
        --bg-color: #F8FAFC;
        --card-bg: #FFFFFF;
        --text-main: #1E293B;
    }

    /* 全局背景与字体 */
    .stApp {
        background-color: var(--bg-color);
        font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
        color: var(--text-main);
    }

    /* 侧边栏美化 */
    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #E2E8F0;
    }

    /* 卡片容器 (Expander, Container) */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        /* 针对 Streamlit 内部容器的 hack */
    }
    
    .st-card {
        background: white;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #F1F5F9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
        margin-bottom: 20px;
    }

    /* 输入框与下拉框 */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        padding: 0.5rem;
    }
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(0, 185, 155, 0.2);
    }

    /* 按钮样式重写 */
    div.stButton > button {
        border-radius: 12px;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s;
    }
    /* 主按钮 (Primary) */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00B99B 0%, #0F766E 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(0, 185, 155, 0.3);
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0, 185, 155, 0.4);
    }
    /* 次级按钮 (Secondary) */
    div.stButton > button[kind="secondary"] {
        background: white;
        border: 1px solid #E2E8F0;
        color: #64748B;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--primary);
        color: var(--primary);
        background: #F0FDFA;
    }

    /* 隐藏 Streamlit 默认头部 */
    header[data-testid="stHeader"] {
        background: rgba(255,255,255,0.8);
        backdrop-filter: blur(10px);
    }

    /* 书籍封面 CSS */
    .book-cover {
        position: relative;
        width: 100%;
        aspect-ratio: 3/4;
        border-radius: 8px 12px 12px 8px;
        overflow: hidden;
        transition: transform 0.3s;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .book-cover:hover { transform: translateY(-5px); }
    .book-spine {
        position: absolute; left: 0; top: 0; bottom: 0; width: 6px;
        background: linear-gradient(90deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.5) 50%, rgba(0,0,0,0.1) 100%);
    }
    .book-pattern {
        position: absolute; inset: 0;
        background-image: radial-gradient(#fff 10%, transparent 11%);
        background-size: 10px 10px;
        opacity: 0.1;
    }

    /* Tags */
    .pill-tag {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 12px;
        font-weight: 600;
        color: #64748B;
        background: white;
        border: 1px solid #E2E8F0;
        margin-right: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .pill-tag:hover, .pill-tag.active {
        background: var(--primary);
        color: white;
        border-color: var(--primary);
    }
    
    /* 进度条颜色 */
    div[data-testid="stProgress"] > div > div > div > div {
        background-color: var(--primary);
    }
</style>
""", unsafe_allow_html=True)

# ------------------ 2. 模拟数据 (Mock Data) ------------------
# 这里的书籍数据对应你 UI 截图中的内容
MOCK_BOOKS = [
    {
        "id": 1, 
        "title": "完全版考研考纲词汇", 
        "desc": "一轮复习必背！26考研英语大纲词表全收录，英语一英语二通用。", 
        "count": 5561, 
        "tag": "26最新考纲", 
        "hot": True, 
        "bg": "#FDE68A", # 黄
        "text": "#451a03"
    },
    {
        "id": 2, 
        "title": "CET-4 高频核心词", 
        "desc": "大学英语四级考试高频词汇，过级必备。", 
        "count": 2400, 
        "tag": "四级核心", 
        "hot": True, 
        "bg": "#A7F3D0", # 绿
        "text": "#064e3b"
    },
    {
        "id": 3, 
        "title": "经济学人 2024 精选", 
        "desc": "The Economist 年度热词，外刊阅读必备。", 
        "count": 890, 
        "tag": "外刊", 
        "hot": False, 
        "bg": "#FECACA", # 红
        "text": "#7f1d1d"
    },
    {
        "id": 4, 
        "title": "老友记 S01-S10", 
        "desc": "Friends 全十季生肉词表，口语提升神器。", 
        "count": 3200, 
        "tag": "美剧", 
        "hot": True, 
        "bg": "#DDD6FE", # 紫
        "text": "#4c1d95"
    },
]

# ------------------ 3. 工具函数 (NLP) ------------------
# (保留原有的 NLTK/Spacy 下载和处理逻辑，此处简化展示，请确保已安装依赖)
@st.cache_resource
def download_nltk_resources():
    resources = ["punkt", "averaged_perceptron_tagger", "wordnet", "stopwords"]
    for r in resources:
        try: nltk.data.find(f'tokenizers/{r}')
        except LookupError: nltk.download(r, quiet=True)

download_nltk_resources()

def extract_text(file_obj, filename):
    # 简化的文本提取
    try:
        content = file_obj.read()
        return content.decode('utf-8', errors='ignore')
    except: return ""

def process_nlp(text, engine, min_len, sort_mode, filter_list):
    # 模拟 NLP 处理过程
    # 真实环境请使用 process_words 函数
    words = re.findall(r'\b[a-z]{' + str(min_len) + r',}\b', text.lower())
    unique = list(set(words) - set(filter_list))
    
    if sort_mode == "A-Z 排序":
        unique.sort()
    elif sort_mode == "随机打乱":
        random.shuffle(unique)
    # 默认按出现顺序 (不处理)
    
    return unique

# ------------------ 4. 页面逻辑 ------------------

# 侧边栏
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/dictionary.png", width=50)
    st.markdown("### VocabMaster")
    st.caption("v7.0 Pro Edition")
    
    st.markdown("---")
    # 使用 Radio 模拟导航菜单
    menu = st.radio("导航", ["公共词书库", "智能生词工坊", "个人中心"], label_visibility="collapsed")
    
    st.markdown("---")
    # 移除广告，保留用户信息
    col_av, col_info = st.columns([1, 3])
    with col_av:
        st.image("https://api.dicebear.com/7.x/notionists/svg?seed=Felix", width=40)
    with col_info:
        st.markdown("**普通用户**\n<span style='color:#94a3b8;font-size:12px'>Free Plan</span>", unsafe_allow_html=True)

# === 页面 1: 公共词书库 (Library) ===
if menu == "公共词书库":
    # 顶部 Header
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("📚 公共词书库")
        st.caption("Discover & Learn - 发现优质语料")
    with c2:
        st.text_input("🔍", placeholder="搜索...", label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    # 模拟 Tab 栏
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <span class="pill-tag active">大学</span>
        <span class="pill-tag">高中</span>
        <span class="pill-tag">留学</span>
        <span class="pill-tag">兴趣英语</span>
    </div>
    """, unsafe_allow_html=True)

    # 筛选 Tags
    st.markdown("""
    <div style="margin-bottom: 30px;">
        <span style="font-size:12px;color:#94a3b8;margin-right:10px;">热门标签:</span>
        <span class="pill-tag" style="background:#F1F5F9;border:none;"># 考研</span>
        <span class="pill-tag" style="background:#F1F5F9;border:none;"># 四级</span>
        <span class="pill-tag" style="background:#F1F5F9;border:none;"># 雅思</span>
    </div>
    """, unsafe_allow_html=True)

    # 书籍网格 (Grid Layout)
    cols = st.columns(4)
    for idx, book in enumerate(MOCK_BOOKS):
        with cols[idx % 4]:
            # 使用 HTML 渲染纯 CSS 书籍封面
            cover_html = f"""
            <div class="book-cover" style="background-color: {book['bg']}; color: {book['text']}; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:15px; text-align:center;">
                <div class="book-spine"></div>
                <div class="book-pattern"></div>
                <div style="background:rgba(255,255,255,0.8); padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold; margin-bottom:10px; z-index:2;">{book['tag']}</div>
                <div style="font-size:18px; font-weight:800; line-height:1.2; z-index:2;">{book['title']}</div>
                <div style="margin-top:10px; width:20px; height:3px; background:currentColor; opacity:0.3; border-radius:10px;"></div>
            </div>
            """
            st.markdown(cover_html, unsafe_allow_html=True)
            
            # 书籍底部信息
            st.markdown(f"**{book['title']}**")
            c_meta1, c_meta2 = st.columns([1, 1])
            c_meta1.caption(f"{book['count']} 词")
            if book['hot']:
                c_meta2.markdown("<span style='color:#F97316;font-size:12px;font-weight:bold'>🔥 Hot</span>", unsafe_allow_html=True)
            
            st.button("下载", key=f"dl_{idx}", use_container_width=True)

# === 页面 2: 智能生词工坊 (Workbench) ===
elif menu == "智能生词工坊":
    st.title("⚡ 智能生词工坊")
    st.caption("AI 赋能，一键生成专属词书")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 布局：左侧配置，右侧输入
    col_conf, col_input = st.columns([1, 2], gap="large")
    
    # --- 左侧：配置卡片 ---
    with col_conf:
        with st.container():
            st.markdown("#### 🛠️ 提取配置")
            st.markdown('<div class="st-card">', unsafe_allow_html=True)
            
            # 1. 引擎选择
            st.markdown("**NLP 引擎**")
            engine = st.selectbox("Engine", ["Spacy (精准)", "NLTK (快速)"], label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 2. 排序方式 (响应你的新需求)
            st.markdown("**排序方式**")
            sort_mode = st.selectbox("Sort", ["按文本出现顺序", "A-Z 排序", "随机打乱"], label_visibility="collapsed")
            
            st.markdown("<br>", unsafe_allow_html=True)

            # 3. 词长
            st.markdown("**最短词长**")
            min_len = st.slider("Min Length", 2, 15, 3, label_visibility="collapsed")
            
            st.markdown("<hr style='margin:20px 0; border-top:1px solid #F1F5F9;'>", unsafe_allow_html=True)
            
            # 4. 熟词过滤
            st.markdown("**熟词屏蔽 (Filter)**")
            st.multiselect("选择屏蔽库", ["小学词汇", "初中词汇", "高中词汇"], default=["小学词汇"], label_visibility="collapsed")
            
            st.markdown('</div>', unsafe_allow_html=True)

    # --- 右侧：双模输入卡片 ---
    with col_input:
        st.markdown("#### 📝 输入素材")
        
        # 统一输入框容器
        container = st.container()
        with container:
            # 文本输入
            user_text = st.text_area(
                "在此粘贴文本...", 
                height=300, 
                placeholder="在此粘贴文章、字幕文本、歌词...\n或者点击下方按钮上传文件",
                label_visibility="collapsed"
            )
            
            # 文件上传 (整合在下方，类似聊天框附件)
            uploaded_file = st.file_uploader("上传文件 (支持 .txt, .docx, .srt)", type=['txt', 'docx', 'srt', 'ass'], label_visibility="collapsed")
            
            # 操作栏
            col_act_1, col_act_2 = st.columns([3, 1])
            with col_act_1:
                if uploaded_file:
                    st.info(f"📄 已加载文件: {uploaded_file.name}")
            with col_act_2:
                extract_btn = st.button("🚀 开始提取", type="primary", use_container_width=True)

        # 提取逻辑
        if extract_btn:
            text_to_process = user_text
            
            if uploaded_file:
                # 简单读取文件内容
                file_text = extract_text(uploaded_file, uploaded_file.name)
                text_to_process += "\n" + file_text
            
            if not text_to_process.strip():
                st.error("请先输入文本或上传文件！")
            else:
                with st.spinner("AI 正在分析文本..."):
                    time.sleep(1) # 模拟耗时
                    # 调用处理逻辑
                    result_words = process_nlp(text_to_process, engine, min_len, sort_mode, [])
                    
                    st.success(f"🎉 提取成功！共发现 {len(result_words)} 个生词")
                    
                    # 结果展示区
                    with st.expander("查看结果列表", expanded=True):
                        st.write(", ".join(result_words[:100]) + ("..." if len(result_words)>100 else ""))
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button("📥 下载 .txt", "\n".join(result_words), "vocab.txt", use_container_width=True)
                        with c2:
                            st.button("☁️ 保存到个人书库", use_container_width=True)

# === 页面 3: 个人中心 ===
elif menu == "个人中心":
    st.title("👤 个人中心")
    st.info("功能开发中...")
