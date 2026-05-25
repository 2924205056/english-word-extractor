"""File parser: extract text from various document formats."""

import chardet
from docx import Document
from PyPDF2 import PdfReader


def extract_text_from_bytes(file_obj, filename):
    """从上传的文件对象中提取文本内容。

    支持: .txt .srt .ass .docx .pdf
    """
    try:
        ext = filename.split('.')[-1].lower()
        if ext == 'docx':
            return "\n".join([p.text for p in Document(file_obj).paragraphs if p.text.strip()])
        if ext == 'pdf':
            reader = PdfReader(file_obj)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        raw = file_obj.read()
        return raw.decode(chardet.detect(raw)['encoding'] or 'utf-8', errors='ignore')
    except Exception:
        return ""
