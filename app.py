"""VocabMaster — Streamlit UI layer (frontend)."""

import io
import csv
import os
import json
import random
import time

import streamlit as st
import streamlit.components.v1 as components

from src.nlp import process_words
from src.parser import extract_text_from_bytes
from src.library import save_to_library, load_book_info, list_books, read_book_content

# ------------------ 0. 初始化 & 资源加载 ------------------
WORDLIST_DIR = "wordlists"
LIBRARY_DIR = "library"
for d in [WORDLIST_DIR, LIBRARY_DIR]:
    if not os.path.exists(d): os.makedirs(d)

if not os.path.exists(os.path.join(WORDLIST_DIR, "primary.txt")):
    with open(os.path.join(WORDLIST_DIR, "primary.txt"), "w", encoding="utf-8") as f:
        f.write("a\nan\nthe\nis\nare\nam\nhello\ngood\nbook\npen")

PRESET_WORDLISTS = {
    "👶 小学核心词": os.path.join(WORDLIST_DIR, "primary.txt"),
    "👦 中考必备词": os.path.join(WORDLIST_DIR, "zhongkao.txt"),
    "👨‍🎓 高考3500词": os.path.join(WORDLIST_DIR, "gaokao.txt"),
}

# ------------------ 1. 深度 CSS 设计系统 ------------------
st.set_page_config(page_title="VocabMaster", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+SC:wght@400;500;700&display=swap');

    .stApp {
        background-color: #F8FAFC;
        font-family: 'Plus Jakarta Sans', 'Noto Sans SC', sans-serif;
        color: #1e293b;
    }

    header[data-testid="stHeader"] { background: transparent; pointer-events: none; }
    .stMain { margin-top: -50px; }

    section[data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid #f1f5f9;
        box-shadow: 2px 0 15px rgba(0,0,0,0.01);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        background-color: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        padding: 24px !important;
    }

    div.stButton > button[kind="primary"] {
        background: #0f172a; color: white; border: none; width: 100%;
        border-radius: 12px; padding: 0.6rem 1.2rem; font-weight: 600;
        transition: all 0.2s;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #334155; transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }

    .stTextInput > div > div, .stSelectbox > div > div, .stNumberInput > div > div {
        background-color: #F8FAFC; border: 1px solid #cbd5e1; border-radius: 10px;
    }

    .stTextArea textarea {
        background-color: #F8FAFC; border: 1px solid #cbd5e1; border-radius: 10px;
        font-family: 'JetBrains Mono', monospace; font-size: 14px;
    }

    [data-testid="stFileUploader"] {
        background-color: #F8FAFC; border: 2px dashed #94a3b8; border-radius: 12px;
        padding: 20px; transition: all 0.3s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #0F766E; background-color: #f0fdfa;
    }

    .top-nav {
        background: rgba(255,255,255,0.8); backdrop-filter: blur(10px);
        padding: 15px 20px; border-bottom: 1px solid #e2e8f0;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 20px; border-radius: 0 0 16px 16px;
    }

    .book-3d {
        width: 100%; aspect-ratio: 3/4; border-radius: 6px 14px 14px 6px;
        position: relative; transition: transform 0.3s; cursor: pointer;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; padding: 10px; box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
    }
    .book-3d:hover { transform: translateY(-5px) scale(1.02); box-shadow: 8px 12px 25px rgba(0,0,0,0.15); }

</style>
""", unsafe_allow_html=True)


# ------------------ 2. UI 辅助函数 ------------------
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
            <div style="width:32px; height:32px; background:#0f172a; color:white;
                        border-radius:6px; display:flex; align-items:center;
                        justify-content:center; font-weight:bold;">V</div>
            <h3 style="margin:0; font-size:18px;">VocabMaster</h3>
        </div>
    """, unsafe_allow_html=True)
    menu = st.radio("MAIN MENU", ["⚡ 智能工作台", "📚 公共词书库", "👤 个人中心"],
                    label_visibility="collapsed")
    st.markdown("---")
    st.info("📢 字幕文件无需转换，直接拖入即可。")

# 顶部导航
st.markdown("""
<div class="top-nav">
    <div style="font-weight:700; color:#334155;">Dashboard</div>
    <div style="font-size:12px; background:white; padding:4px 10px;
                border-radius:20px; border:1px solid #e2e8f0;">User: Free Plan</div>
</div>
""", unsafe_allow_html=True)


# === ⚡ 智能工作台 ===
if "工作台" in menu:

    with st.expander("📖 新手指南 & 宝藏资源库 (点击展开)", expanded=False):
        t1, t2, t3, t4 = st.tabs(["💡 操作指引", "🎬 影视字幕", "📚 原著阅读", "🎧 听力素材"])

        with t1:
            st.markdown("""
            <div style="padding:5px;">
            <h5 style="margin-top:0">🚀 四步制作专属词书：</h5>
            <ol>
                <li><b>准备素材</b>：从右侧标签页下载 <code>.srt</code> 字幕或 <code>.txt</code> 电子书。</li>
                <li><b>清洗设置</b>：在下方【设置提取规则】中，选择<b>"预置熟词库"</b>或上传自定义熟词表（非常重要！能屏蔽掉 is, the 等简单词）。</li>
                <li><b>智能提取</b>：将文件拖入上传区，AI 自动完成去重、词形还原（Run/Ran/Running → Run）。</li>
                <li><b>闭环学习</b>：点击生成的<b>"一键复制"</b>按钮，跳转扇贝网批量制卡，或导出词书。</li>
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

    # 主操作区
    if 'result_words' not in st.session_state:
        st.session_state.result_words = []

    col_conf, col_input = st.columns([1, 2], gap="medium")

    with col_conf:
        with st.container(border=True):
            st.markdown("##### 🛠️ 提取配置")
            nlp_mode = st.selectbox("AI 引擎", ["nltk (快速)", "spacy (精准)"])
            sort_order = st.selectbox("排序", ["按词频排序", "A-Z 排序", "随机打乱"])
            min_len = st.slider("最短词长", 2, 15, 3)

            st.divider()
            st.markdown("##### 🎨 显示选项")
            show_freq = st.checkbox("📊 显示词频", value=False)
            show_examples = st.checkbox("📝 匹配例句", value=False)

            st.divider()
            st.markdown("##### 🛡️ 熟词屏蔽")
            selected_presets = st.multiselect("预置库", PRESET_WORDLISTS.keys(), default=[])
            filter_file = st.file_uploader("自定义屏蔽表 (.txt)", type=['txt'])

    with col_input:
        with st.container(border=True):
            st.markdown("""
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <b>📄 输入源 (Input Source)</b>
                <span style="font-size:12px; color:#64748b; background:#f1f5f9;
                             padding:2px 6px; border-radius:4px;">支持 .txt .srt .docx .pdf</span>
            </div>
            """, unsafe_allow_html=True)

            tab_txt, tab_file = st.tabs(["✍️ 粘贴文本", "📂 上传文件"])
            with tab_txt:
                input_text = st.text_area("粘贴区域", height=250,
                                          placeholder="在此直接粘贴文章、字幕文本...",
                                          label_visibility="collapsed")
            with tab_file:
                uploaded_files = st.file_uploader(
                    "拖拽区域", type=['txt', 'srt', 'ass', 'docx', 'pdf'],
                    accept_multiple_files=True, label_visibility="collapsed")

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
                    with open(PRESET_WORDLISTS[p], 'r', encoding='utf-8') as f:
                        filter_set.update(f.read().splitlines())
            if filter_file:
                filter_set.update(filter_file.getvalue().decode('utf-8', errors='ignore').splitlines())

            mode_key = "spacy" if "spacy" in nlp_mode else "nltk"

            # spaCy 进度条
            progress_bar = st.progress(0) if mode_key == "spacy" else None
            with st.spinner("正在词性还原中..."):
                words = process_words(full_text, mode_key, min_len, filter_set,
                                      progress_cb=lambda r: progress_bar.progress(r)
                                      if progress_bar else None,
                                      with_examples=show_examples)
            if progress_bar:
                progress_bar.empty()

            if sort_order == "A-Z 排序":
                words.sort(key=lambda x: x[0])
            elif sort_order == "随机打乱":
                random.shuffle(words)

            st.session_state.result_words = words
            st.session_state.show_freq = show_freq
            st.session_state.show_examples = show_examples
            st.rerun()

    # 结果展示
    if st.session_state.result_words:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            words = st.session_state.result_words
            _freq = st.session_state.get("show_freq", False)
            _ex = st.session_state.get("show_examples", False)

            # 按选项生成展示文本
            lines = []
            for w, c, s in words:
                line = w
                if _freq:
                    line += f" ({c})"
                if _ex and s:
                    line += f"  — {s}"
                lines.append(line)
            display_str = "\n".join(lines)
            plain_str = "\n".join([w for w, _, _ in words])

            st.markdown(f"### 🎉 提取结果 (共 {len(words)} 词)")
            st.text_area("Result", value=display_str, height=200, label_visibility="collapsed")

            if _freq:
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    copy_btn(plain_str)
                with c2:
                    st.download_button("📦 下载 .txt", plain_str, "vocab.txt",
                                       "text/plain", use_container_width=True)
                with c3:
                    csv_buf = io.StringIO()
                    writer = csv.writer(csv_buf)
                    header = ["word", "frequency"]
                    if _ex: header.append("sentence")
                    writer.writerow(header)
                    for w, c, s in words:
                        row = [w, c]
                        if _ex: row.append(s)
                        writer.writerow(row)
                    csv_data = csv_buf.getvalue()
                    st.download_button("📊 下载 CSV", csv_data, "vocab.csv",
                                       "text/csv", use_container_width=True)
            else:
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    copy_btn(plain_str)
                with c2:
                    st.download_button("📦 下载 .txt", plain_str, "vocab.txt",
                                       "text/plain", use_container_width=True)
                with c3:
                    with st.popover("☁️ 发布到社区库", use_container_width=True):
                        with st.form("pub_form"):
                            name = st.text_input("文件名 (英文, e.g. friends_s1.txt)",
                                                f"list_{int(time.time())}.txt")
                            title = st.text_input("标题")
                            desc = st.text_area("描述")
                            if st.form_submit_button("发布"):
                                if name.endswith(".txt"):
                                    secrets = None
                                    if "GITHUB_TOKEN" in st.secrets:
                                        secrets = {
                                            "GITHUB_TOKEN": st.secrets["GITHUB_TOKEN"],
                                            "GITHUB_USERNAME": st.secrets["GITHUB_USERNAME"],
                                            "GITHUB_REPO": st.secrets["GITHUB_REPO"],
                                        }
                                    success, msg, cloud = save_to_library(
                                        name, plain_str, title, desc, LIBRARY_DIR, secrets)
                                    if success:
                                        if cloud:
                                            st.toast("✅ 云端发布成功！", icon="🎉")
                                        else:
                                            st.toast("⚠️ 无 GitHub Token，仅保存到本地。", icon="📂")
                                        time.sleep(0.3)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.error("文件名需以 .txt 结尾")


# === 📚 公共词书库 ===
elif "词书库" in menu:
    with st.container(border=True):
        q = st.text_input("搜索", placeholder="🔍 搜索书名...", label_visibility="collapsed")

    visible, book_info = list_books(LIBRARY_DIR, q)

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
                    <h4 style="margin:0; font-size:16px; overflow:hidden;
                               text-overflow:ellipsis; white-space:nowrap; width:100%;">{title}</h4>
                    <p style="font-size:12px; opacity:0.8; margin-top:5px;
                              height:36px; overflow:hidden;">{desc[:40]}...</p>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("操作"):
                    try:
                        content = read_book_content(LIBRARY_DIR, f)
                        st.caption(f"文件名: {f}")
                        st.download_button("⬇️ 下载", content, f)
                        copy_btn(content)
                    except Exception:
                        st.error("文件读取失败")

else:
    st.info("🚧 个人中心开发中...")
