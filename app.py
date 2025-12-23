91
92
93
94
95
96
97
98
99
100
101
102
103
104
105
106
107
108
109
110
111
112
113
114
115
116
117
118
119
120
121
122
123
124
125
126
127
128
129
130
131
132
133
134
135
136
137
138
139
140
141
142
143
144
145
146
147
148
149
150
151
152
153
154
155
156
157
158
159
160
161
162
163
164
165
166
167
168
169
170
171
172
173
174
175
176
177
178
179
180
181
182
183
184
185
186
187
188
189
190
191
192
193
194
195
196
197
198
199
200
201
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

        time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"发布过程中出现错误: {e}")

def extract_text_from_bytes(file_obj, filename):
    try:
