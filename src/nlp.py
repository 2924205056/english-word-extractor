"""NLP engine: lemmatization, word extraction, example matching."""

import re
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet, stopwords
from nltk import pos_tag, sent_tokenize

try:
    import spacy
    _HAS_SPACY = True
except ImportError:
    _HAS_SPACY = False


def _download_nltk_resources():
    resources = ["punkt", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng",
                 "wordnet", "omw-1.4", "stopwords"]
    for r in resources:
        try:
            nltk.data.find(f'tokenizers/{r}')
        except (LookupError, ValueError):
            nltk.download(r, quiet=True)


def _load_spacy_model():
    if not _HAS_SPACY:
        return None
    for model in ("en_core_web_trf", "en_core_web_md", "en_core_web_sm"):
        try:
            return spacy.load(model, disable=["ner", "parser"] if model == "en_core_web_sm" else [])
        except OSError:
            continue
    return None


_download_nltk_resources()
nlp_spacy = _load_spacy_model()


def get_wordnet_pos(treebank_tag):
    """将 Penn Treebank POS 标签映射为 WordNet POS，用于精准词形还原。"""
    if treebank_tag.startswith('J'): return wordnet.ADJ
    if treebank_tag.startswith('V'): return wordnet.VERB
    if treebank_tag.startswith('R'): return wordnet.ADV
    return wordnet.NOUN


def extract_examples(text, word_counts):
    """为每个词提取第一条包含它的例句。"""
    try:
        sentences = sent_tokenize(text)
    except Exception:
        return {}
    examples = {}
    words_needed = set(word_counts)
    for sent in sentences:
        if not words_needed:
            break
        sent_lower = sent.lower()
        for word in list(words_needed):
            if re.search(r'\b' + re.escape(word) + r'\b', sent_lower):
                examples[word] = sent[:200] + ("…" if len(sent) > 200 else "")
                words_needed.discard(word)
    return examples


def process_words(text, mode, min_len, filter_set=None, progress_cb=None, with_examples=False):
    """提取文本中的英文词汇，词形还原、去重、词频统计。

    Args:
        text: 输入文本
        mode: "spacy" | "nltk"
        min_len: 最短词长
        filter_set: 要过滤掉的熟词集合
        progress_cb: 可选，spaCy 模式下回调 progress_cb(ratio)
        with_examples: 是否匹配例句（默认 False，跳过以提升速度）

    Returns:
        [(word, count, sentence), ...] 按词频降序，sentence 为空字符串当 with_examples=False
    """
    word_counts = {}
    stops = set(stopwords.words('english'))

    if mode == "spacy" and nlp_spacy:
        nlp_spacy.max_length = 2000000
        chunk_size = 100000
        text_chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        for i, chunk in enumerate(text_chunks):
            if progress_cb:
                progress_cb((i + 1) / len(text_chunks))
            doc = nlp_spacy(chunk)
            for token in doc:
                if (token.is_alpha and not token.is_stop and
                        len(token.text) >= min_len and
                        token.pos_ in ('NOUN', 'VERB', 'ADJ', 'ADV')):
                    lemma = token.lemma_.lower()
                    if not re.match(r"^[a-z]+$", lemma):
                        continue
                    if filter_set and lemma in filter_set:
                        continue
                    word_counts[lemma] = word_counts.get(lemma, 0) + 1

    else:
        tokens = [w.lower() for w in re.findall(r"[A-Za-z-]+", text) if w]
        tagged = pos_tag(tokens)
        l = WordNetLemmatizer()
        for word, tag in tagged:
            clean = re.sub(r'[^a-z]', '', word)
            if len(clean) < min_len or clean in stops:
                continue
            lemma = l.lemmatize(clean, get_wordnet_pos(tag))
            if not re.match(r"^[a-z]+$", lemma):
                continue
            if filter_set and lemma in filter_set:
                continue
            word_counts[lemma] = word_counts.get(lemma, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

    examples = {}
    if with_examples:
        examples = extract_examples(text, dict(sorted_words))

    return [(w, c, examples.get(w, "")) for w, c in sorted_words]
