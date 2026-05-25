"""Library management: local file storage + GitHub sync."""

import os
import json
import time
from github import Github


def load_book_info(library_dir):
    """读取词书库元数据。"""
    info_path = os.path.join(library_dir, "info.json")
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def list_books(library_dir, query=""):
    """列出词书库中所有书籍，支持搜索。"""
    info = load_book_info(library_dir)
    try:
        files = [f for f in os.listdir(library_dir) if f.endswith(".txt")]
    except FileNotFoundError:
        return [], {}
    q = query.lower()
    visible = [f for f in files
               if q in f.lower() or q in info.get(f, {}).get("title", "").lower()]
    return visible, info


def read_book_content(library_dir, filename):
    """读取词书文件内容。"""
    path = os.path.join(library_dir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_to_library(filename, content, title, desc, library_dir, secrets=None):
    """保存词书到本地 + 可选的 GitHub 云端同步。

    Returns:
        (success: bool, message: str, cloud_saved: bool)
    """
    cloud_saved = False

    # GitHub 云端同步
    if secrets and all(k in secrets for k in ("GITHUB_TOKEN", "GITHUB_USERNAME", "GITHUB_REPO")):
        try:
            g = Github(secrets["GITHUB_TOKEN"])
            repo = g.get_repo(f"{secrets['GITHUB_USERNAME']}/{secrets['GITHUB_REPO']}")

            try:
                repo.create_file(f"library/{filename}", f"Create {filename}", content)
            except Exception:
                repo.update_file(f"library/{filename}", f"Update {filename}",
                                 content, repo.get_contents(f"library/{filename}").sha)

            info_path = "library/info.json"
            try:
                c = repo.get_contents(info_path)
                info = json.loads(c.decoded_content.decode())
            except Exception:
                info = {}
            info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
            try:
                repo.update_file(info_path, "Update info",
                                 json.dumps(info, ensure_ascii=False, indent=2),
                                 repo.get_contents(info_path).sha)
            except Exception:
                repo.create_file(info_path, "Init info",
                                 json.dumps(info, ensure_ascii=False, indent=2))
            cloud_saved = True
        except Exception:
            pass

    # 本地保存
    os.makedirs(library_dir, exist_ok=True)
    with open(os.path.join(library_dir, filename), "w", encoding="utf-8") as f:
        f.write(content)

    local_info_path = os.path.join(library_dir, "info.json")
    try:
        with open(local_info_path, "r", encoding="utf-8") as f:
            local_info = json.load(f)
    except Exception:
        local_info = {}
    local_info[filename] = {"title": title, "desc": desc, "date": time.strftime("%Y-%m-%d")}
    with open(local_info_path, "w", encoding="utf-8") as f:
        json.dump(local_info, f, indent=2, ensure_ascii=False)

    return True, "发布成功！", cloud_saved
