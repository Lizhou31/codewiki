"""HTML-only translations; canonical documents remain the query/review model."""
from __future__ import annotations

import copy
import posixpath
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Regional suffixes avoid treating ordinary hyphenated page names as locales.
SUFFIX = re.compile(r"^(.*)-([a-z]{2,3}_[a-z]{2})$", re.I)


def translation_source(path):
    match = SUFFIX.fullmatch(path.stem)
    if not match:
        return None
    stem, locale = match.groups()
    locale = locale.lower()
    if locale == "zh_tw":
        locale = "ch_tw"
    return path.with_name(stem + path.suffix), locale


def language_tag(locale):
    return "zh-TW" if locale == "ch_tw" else "-".join(
        part.upper() if i else part for i, part in enumerate(locale.split("_")))


def language_label(locale):
    return {"en": "English", "ch_tw": "繁體中文（台灣）"}.get(locale, language_tag(locale))


def page_name(name, locale):
    return name if locale == "en" else f"{Path(name).stem}-{locale}.html"


# @wiki:impl renderer.translations
def load_translations(w, docs, warns):
    from .build import Warning, parse_doc
    canonical = {w.abs(d.path): d for d in docs}
    translations = {}
    for path in sorted(w.wiki_dir.rglob("*.md")):
        if any(part.startswith("_") for part in path.relative_to(w.wiki_dir).parts):
            continue
        match = translation_source(path)
        if not match:
            continue
        source, locale = match
        if source.name.upper() in ("README.MD", "TAGS.MD"):
            continue
        original = canonical.get(source.resolve())
        if original is None:
            warns.append(Warning("invalid-translation", "translation needs a canonical English sibling", w.rel(path)))
            continue
        translated = parse_doc(w, path, warns)
        if translated is None:
            continue
        expected = [(s["slug"], s["level"]) for s in original.outline]
        actual = [(s["slug"], s["level"]) for s in translated.outline]
        if translated.id != original.id or actual != expected:
            warns.append(Warning("invalid-translation", "preserve the English document id and all heading anchors, levels, and order", w.rel(path)))
            continue
        variants = translations.setdefault(locale, {})
        if original.id in variants:
            warns.append(Warning("invalid-translation", "duplicate translation for this language", w.rel(path)))
            continue
        variants[original.id] = translated
    return translations


def localized_docs(docs, variants, locale):
    result = copy.deepcopy(docs)
    for doc in result:
        doc.out = page_name(doc.out, locale)
        translated = variants.get(doc.id)
        doc.content_language = language_tag(locale if translated else "en")
        doc.translation_missing = translated is None and locale != "en"
        if translated is None:
            continue
        english_outline = doc.outline
        doc.path, doc.title = translated.path, translated.title
        doc.markdown = translated.markdown
        doc.preamble = translated.preamble
        doc.outline = copy.deepcopy(translated.outline)
        doc.sections = copy.deepcopy(translated.sections)
        for section, original in zip(doc.outline, english_outline):
            section["kind"] = original["kind"]
            section["explicit"] = original["explicit"]
        doc.tldr = [line.strip()[2:].strip() for section in doc.outline
                    if section["slug"] == "tl-dr" for line in section["body"].splitlines()
                    if line.strip().startswith("- ")]
        doc.summary = translated.summary or " ".join(doc.tldr) or doc.summary
        for section in doc.outline:
            anchor = doc.anchors.get(section["id"])
            if anchor:
                anchor.title, anchor.body_html = section["title"], section["body_html"]
        # Authored rationale can be translated; references still come from English.
        reasons = {d["id"]: d["reason"] for d in translated.decisions}
        for decision in doc.decisions:
            decision["reason"] = reasons.get(decision["id"], decision["reason"])
    return result


def localize_links(markup, doc, docs, locale):
    """Rewrite only actual HTML anchor hrefs, never code text or external URLs."""
    from html import escape, unescape
    from html.parser import HTMLParser

    html_pages = {d.out: page_name(d.out, locale) for d in docs}
    html_pages.update({name: page_name(name, locale) for name in ("index.html", "files.html")})
    markdown_pages = {posixpath.normpath(d.path): page_name(d.out, locale) for d in docs}
    replacements = []
    lines = markup.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            raw = self.get_starttag_text()
            match = re.search(r'(?<![\w:-])href\s*=\s*([\"\'])(.*?)\1', raw, re.I | re.S)
            if not match:
                return
            url = urlsplit(unescape(match[2]))
            if url.scheme or url.netloc or not url.path:
                return
            dest = html_pages.get(url.path)
            if not dest and doc:
                path = posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), url.path))
                dest = markdown_pages.get(path)
            if dest:
                line, column = self.getpos()
                start = offsets[line - 1] + column
                replacements.append((start + match.start(2), start + match.end(2),
                                     escape(urlunsplit(("", "", dest, url.query, url.fragment)), quote=True)))

    Links().feed(markup)
    for start, end, value in reversed(replacements):
        markup = markup[:start] + value + markup[end:]
    return markup
