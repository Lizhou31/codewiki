"""Code_Wiki build: markdown + code tags -> index.json + static HTML.

    python -m codewiki build            # build
    python -m codewiki build --strict   # exit non-zero on any error
    python -m codewiki build --config path/to/wiki.config.yaml
"""
from __future__ import annotations

import argparse, fnmatch, html, json, posixpath, re, shutil, sys, time
import copy
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor
import xml.etree.ElementTree as etree
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError

from .config import Wiki, load as load_wiki
from .documents import read_document
from .localization import (translation_source, load_translations, localized_docs,
                           localize_links, page_name, language_tag, language_label)
from .snapshot import snapshot
from .languages import (DEFAULT_FILE_MAP, LANGUAGES, language_for, parse_tag_comment)

HEADING_RE = re.compile(r'^(#{2,4})\s+(.*?)(?:\s*\{#([A-Za-z0-9_\-.]+)\})?\s*$')
FENCE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
# A relative `.svg` image alone on its line is a figure; remote and absolute images stay images.
SVG_FIGURE_RE = re.compile(r'^ {0,3}!\[([^\]]*)\]\((?![a-zA-Z][a-zA-Z0-9+.-]*:|/)([^)\s]+\.svg)\)\s*$', re.I)
KNOWN_ROLES = {"impl", "gotcha", "entry"}

# --------------------------------------------------------------------------- #
# data model
# --------------------------------------------------------------------------- #

@dataclass
class Tag:
    role: str
    anchor: str            # fully qualified: <doc-id>.<slug>
    file: str              # wiki-root relative
    symbol: str | None
    kind: str
    line_start: int
    line_end: int
    note: str = ""
    code: str = ""
    lang: str = "c"
    hljs: str = "c"

@dataclass
class Ref:
    file: str
    symbol: str
    kind: str = "symbol"
    line_start: int = 0
    line_end: int = 0
    code: str = ""
    resolved: bool = False
    hljs: str = "c"

@dataclass
class Anchor:
    slug: str
    full_id: str
    title: str
    kind: str              # concept | gotcha | other
    doc_id: str
    body_html: str = ""
    impls: list = field(default_factory=list)

@dataclass
class Doc:
    id: str
    title: str
    type: str
    status: str
    path: str
    out: str
    tldr: list = field(default_factory=list)
    owns: list = field(default_factory=list)
    refs: list = field(default_factory=list)
    related: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)
    diagram_links: dict = field(default_factory=dict)
    diagram_groups: dict = field(default_factory=dict)
    group: str | None = None           # as authored; group_name/group_color are inherited
    group_name: str | None = None
    group_color: str | None = None
    figures: list = field(default_factory=list)   # wiki-root-relative SVG figure paths
    updated: str = ""
    summary: str = ""
    parent: str | None = None
    markdown: str = ""
    preamble: str = ""
    outline: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    anchors: dict = field(default_factory=dict)

@dataclass
class Warning:
    kind: str
    message: str
    where: str = ""

SEVERITY = {
    "invalid-translation": "error", "duplicate-anchor": "error", "orphan-tag": "error", "no-id": "error",
    "no-frontmatter": "error", "broken-ref": "error", "missing-file": "error",
    "double-owned": "error", "unknown-role": "error", "tag-in-readonly": "error",
    "missing-root": "error", "invalid-doc": "error", "duplicate-doc": "error",
    "broken-related": "error", "broken-parent": "error", "hierarchy-cycle": "error",
    "broken-decision": "error", "broken-dependency": "error", "broken-diagram-link": "error",
    "unknown-group": "error", "missing-figure": "error", "invalid-figure": "error",
    "broken-figure-link": "error",
    "anchorless-heading": "warn", "outdated-doc": "warn", "unreviewed-doc": "info", "parse-error": "warn",
    "unimplemented": "info",
}

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def matches_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs or [])


def _snippet(src: bytes, start: int, end: int, max_lines: int) -> str:
    code = src[start:end].decode("utf8", "replace")
    lines = code.splitlines()
    if max_lines and len(lines) > max_lines:
        rest = len(lines) - max_lines
        lines = lines[:max_lines] + [f"… (+{rest} lines, open the file)"]
        code = "\n".join(lines)
    return code

# --------------------------------------------------------------------------- #
# code scanning
# --------------------------------------------------------------------------- #

def iter_source_files(w: Wiki, warns: list[Warning]):
    cfg = w.cfg
    file_map = dict(DEFAULT_FILE_MAP)
    file_map.update(cfg.get("languages") or {})
    excl = cfg.get("exclude_globs") or []
    seen = set()
    for root in cfg["code_roots"]:
        base = w.abs(root)
        if not base.exists():
            warns.append(Warning("missing-root", f"code root '{root}' does not exist", w.rel(w.cfg_path)))
            continue
        if base.is_file():
            cands = [base]
        else:
            cands = sorted(p for p in base.rglob("*") if p.is_file())
        for p in cands:
            if p in seen:
                continue
            lang = language_for(p, file_map)
            if lang is None:
                continue
            relp = w.rel(p)
            if matches_any(relp, excl) or any(part in ("site", ".git", "__pycache__") for part in p.parts):
                continue
            seen.add(p)
            yield p, relp, lang


# @wiki:impl languages.registry
def scan_code(w: Wiki) -> tuple[list[Tag], dict, list[Warning], int]:
    tags: list[Tag] = []
    symbols: dict[str, dict] = {}
    warns: list[Warning] = []
    max_lines = int(w.cfg.get("max_snippet_lines") or 0)
    readonly = w.cfg.get("readonly_globs") or []
    nfiles = 0

    for path, relp, lang in iter_source_files(w, warns):
        nfiles += 1
        src = path.read_bytes()
        try:
            comments, targets = lang.scan(src)
        except Exception as e:                       # grammar missing / crash: keep going
            warns.append(Warning("parse-error", f"{lang.name}: {e}", relp))
            continue

        # tags
        file_tags = []
        for c in comments:
            tlist, note = parse_tag_comment(c.text, lang.comment_strip)
            if not tlist:
                continue
            t = c.target
            for role, anchor in tlist:
                if role not in KNOWN_ROLES:
                    warns.append(Warning("unknown-role", f"unknown role '@wiki:{role}'",
                                         f"{relp}:{c.line_start}"))
                if t is None:
                    file_tags.append(Tag(role, anchor, relp, None, "file",
                                         c.line_start, c.line_end, note, "", lang.name, lang.hljs))
                else:
                    file_tags.append(Tag(role, anchor, relp, t.symbol, t.kind,
                                         t.line_start, t.line_end, note,
                                         _snippet(src, t.start_byte, t.end_byte, max_lines),
                                         lang.name, lang.hljs))
        if file_tags and matches_any(relp, readonly):
            for t in file_tags:
                warns.append(Warning("tag-in-readonly",
                    "@wiki tag inside read-only path; use a doc-side ref instead",
                    f"{relp}:{t.line_start}"))
        tags.extend(file_tags)

        # symbol table for doc-side refs: qualified names always, bare names when unique
        table: dict[str, dict] = {}
        bare_count: dict[str, int] = {}
        for t in targets:
            if not t.toplevel:
                continue
            if t.symbol:
                bare_count[t.symbol] = bare_count.get(t.symbol, 0) + 1
        for t in targets:
            if not t.toplevel or not (t.symbol or t.qualified):
                continue
            entry = dict(kind=t.kind, line_start=t.line_start, line_end=t.line_end,
                         start_byte=t.start_byte, end_byte=t.end_byte, lang=lang.name,
                         symbol=t.symbol, qualified=t.qualified or t.symbol,
                         code=_snippet(src, t.start_byte, t.end_byte, max_lines), hljs=lang.hljs)
            if t.qualified and t.qualified not in table:
                table[t.qualified] = entry
            if t.symbol and bare_count.get(t.symbol) == 1 and t.symbol not in table:
                table[t.symbol] = entry
            elif t.symbol and t.symbol not in table:
                # first definition wins for duplicated bare names (e.g. prototype + definition):
                # prefer the definition-ish kinds
                table.setdefault(t.symbol, entry)
        symbols[relp] = table
    return tags, symbols, warns, nfiles

# --------------------------------------------------------------------------- #
# markdown scanning
# --------------------------------------------------------------------------- #

CALLOUT_RE = re.compile(r'^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(?:\n|$)', re.I)
CALLOUT_TITLES = {"note": "Note", "tip": "Tip", "important": "Important", "warning": "Warning", "caution": "Caution"}
CAPTION_RE = re.compile(r'^Figure:[ \t]*(.*)$')
FIGURE_LABEL_RE = re.compile(r'<span class="figure-label">Figure (\d+)\.</span>')
DIAGRAM_HINT = 'Follow a linked node to explore its component or implementation.'
FIGURE_SRC_RE = re.compile(r'<div class="svg-figure" data-figure-src="([^"]*)" data-figure-alt="([^"]*)"></div>')


class _Callouts(Treeprocessor):
    """GitHub alert syntax (`> [!NOTE]`) becomes a labelled notice; other quotes stay quotes."""
    def run(self, root):
        for quote in list(root.iter("blockquote")):
            first = quote[0] if len(quote) else None
            match = CALLOUT_RE.match(first.text or "") if first is not None and first.tag == "p" else None
            if not match:
                continue
            kind = match.group(1).lower()
            first.text = first.text[match.end():]
            if not first.text.strip() and not len(first):
                quote.remove(first)
            quote.tag = "div"
            quote.set("class", f"callout callout-{kind}")
            quote.set("role", "note")
            title = etree.Element("p", {"class": "callout-title"})
            title.text = CALLOUT_TITLES[kind]
            quote.insert(0, title)


class _QuoteBreaks(Preprocessor):
    """As on GitHub, a blank line ends a blockquote; Python-Markdown would merge the next one into it."""
    def run(self, lines):
        out, in_quote, blank = [], False, False
        for line in lines:
            if not line.strip():
                blank = True
                out.append(line)
                continue
            quote = line.startswith(">")
            if quote and blank and in_quote:
                out.extend(["<!-- -->", ""])
            in_quote, blank = quote or (in_quote and not blank), False
            out.append(line)
        return out


class _CalloutExtension(Extension):
    def extendMarkdown(self, md):
        # After fenced code is stashed, before raw HTML blocks are collected.
        md.preprocessors.register(_QuoteBreaks(md), "codewiki-quote-breaks", 22)
        # Before inline parsing, so the marker is still plain paragraph text.
        md.treeprocessors.register(_Callouts(md), "codewiki-callouts", 25)


MD = md_lib.Markdown(extensions=["fenced_code", "tables", "attr_list", "sane_lists", _CalloutExtension()])

def render_md(text: str) -> str:
    MD.reset()
    return MD.convert(text)


def localize_generated(markup: str, locale: str) -> str:
    """Translate labels the renderer generated inside authored Markdown sections."""
    from .ui_text import translate
    markup = markup.replace(DIAGRAM_HINT, translate(DIAGRAM_HINT, locale))
    markup = FIGURE_LABEL_RE.sub(lambda m: '<span class="figure-label">%s</span>'
                                 % translate("Figure {n}.", locale).format(n=m.group(1)), markup)
    for title in CALLOUT_TITLES.values():
        markup = markup.replace(f'<p class="callout-title">{title}</p>',
                                f'<p class="callout-title">{translate(title, locale)}</p>')
    return markup

def split_blocks(lines: list[str]):
    """Separate Mermaid fences and standalone SVG figures; every other fence stays Markdown."""
    out, buf, fence = [], [], None       # fence: (marker, is_mermaid)
    def flush(kind):
        if buf:
            out.append((kind, buf[:]))
            buf.clear()
    for line in lines:
        marker = FENCE_RE.match(line)
        if fence:
            run, rest = marker.groups() if marker else ("", "x")
            if run[:1] == fence[0][0] and len(run) >= len(fence[0]) and not rest.strip():
                if fence[1]:
                    flush("mermaid")
                else:
                    buf.append(line)
                fence = None
            else:
                buf.append(line)
            continue
        if marker:
            fence = (marker.group(1), marker.group(2).strip() == "mermaid")
            if fence[1]:
                flush("md")
            else:
                buf.append(line)
            continue
        if SVG_FIGURE_RE.match(line):
            flush("md")
            out.append(("svg", [line]))
            continue
        buf.append(line)
    flush("mermaid" if fence and fence[1] else "md")
    return out

def take_caption(lines: list[str]) -> tuple[str | None, list[str]]:
    """Split a leading `Figure:` paragraph from the Markdown that follows a diagram."""
    start = next((i for i, line in enumerate(lines) if line.strip()), len(lines))
    match = CAPTION_RE.match(lines[start].strip()) if start < len(lines) else None
    if not match:
        return None, lines
    stop = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    caption = " ".join([match.group(1), *(line.strip() for line in lines[start + 1:stop])]).strip()
    return caption, lines[stop:]


# @wiki:impl renderer.markdown
def render_body(lines: list[str], figures: list[int] | None = None) -> tuple[str, list[str]]:
    """Render Markdown and Mermaid; `figures` carries caption numbering across a page's sections."""
    figures = [0] if figures is None else figures
    parts, mermaids, after_diagram = [], [], False
    for kind, chunk in split_blocks(lines):
        if kind == "md" and after_diagram:
            caption, chunk = take_caption(chunk)
            if caption is not None:
                figures[0] += 1
                inline = re.sub(r"^<p>(.*)</p>$", r"\1", render_md(caption).strip(), flags=re.S)
                parts[-1] = ('<figure class="diagram-figure">%s<figcaption><span class="figure-label">'
                             'Figure %d.</span> %s</figcaption></figure>' % (parts[-1], figures[0], inline))
        after_diagram = False
        text = "\n".join(chunk).strip("\n")
        if not text.strip():
            continue
        if kind == "mermaid":
            mermaids.append(text)
            parts.append(
                '<div class="mermaid-wrap"><pre class="mermaid">%s</pre>'
                '<p class="mermaid-hint">%s</p></div>' % (html.escape(text), DIAGRAM_HINT))
            after_diagram = True
        elif kind == "svg":
            # A placeholder; the renderer inlines the validated file for each language.
            alt, src = SVG_FIGURE_RE.match(text).groups()
            parts.append('<div class="svg-figure" data-figure-src="%s" data-figure-alt="%s"></div>'
                         % (html.escape(src, quote=True), html.escape(alt, quote=True)))
            after_diagram = True
        else:
            parts.append(render_md(text))
    return "\n".join(parts), mermaids

def parse_doc(w: Wiki, path: Path, warns: list[Warning]) -> Doc | None:
    try:
        fm, raw, preamble, outline = read_document(path)
    except ValueError as exc:
        warns.append(Warning("invalid-doc", str(exc), w.rel(path)))
        return None
    doc = Doc(
        id=fm["id"], title=fm.get("title", fm["id"]),
        type=fm.get("type", "component"), status=fm.get("status", "draft"),
        path=w.rel(path), out=f"{fm['id']}.html",
        owns=[w.rel(w.root / x) for x in fm.get("owns", [])],
        related=fm.get("related", []), updated=str(fm.get("updated", "")),
        depends_on=fm.get("depends_on", []), diagram_links=fm.get("diagram_links", {}),
        diagram_groups=fm.get("diagram_groups", {}), group=fm.get("group"),
        summary=fm.get("summary", ""), parent=fm.get("parent"),
        markdown=raw, preamble=render_md(preamble), outline=outline,
        decisions=fm.get("decisions", []),
    )
    for r in fm.get("refs", []):
        for sym in r["symbols"]:
            doc.refs.append(Ref(file=w.rel(w.root / r["file"]), symbol=sym))
    figures = [0]
    for section in outline:
        section["body_html"], _ = render_body(section["body"].splitlines(), figures)
        for src, _ in FIGURE_SRC_RE.findall(section["body_html"]):
            figure = posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), html.unescape(src)))
            if figure not in doc.figures:
                doc.figures.append(figure)
        if section["title"].lower() == "tl;dr":
            doc.tldr = [line.strip()[2:].strip() for line in section["body"].splitlines()
                        if line.strip().startswith("- ")]
        if section["explicit"]:
            aid = section["id"]
            doc.anchors[aid] = Anchor(section["slug"], aid, section["title"],
                                      section["kind"], doc.id, section["body_html"])
        elif section["kind"] in ("concept", "gotcha") and section["level"] >= 3:
            warns.append(Warning("anchorless-heading", f"'{section['title']}' has no {{#slug}}", doc.path))
    if not doc.summary:
        doc.summary = " ".join(doc.tldr)
    # Preserve the original theme contract for existing project overrides.
    current = None
    for section in outline:
        if section["level"] == 2:
            current = dict(section, children=[])
            doc.sections.append(current)
        elif section["level"] == 3 and current is not None:
            current["children"].append(dict(section, full_id=section["id"] if section["explicit"] else None))
    return doc

# --------------------------------------------------------------------------- #
# join + validate
# --------------------------------------------------------------------------- #

# @wiki:impl documents.validation
def join(w: Wiki, docs: list[Doc], tags: list[Tag], symbols: dict) -> list[Warning]:
    warns: list[Warning] = []
    anchors = {}
    by_id = {}
    for d in docs:
        if d.id in by_id:
            warns.append(Warning("duplicate-doc", f"duplicate document id '{d.id}'", d.path))
        by_id[d.id] = d
    destinations = diagram_destinations(docs)
    groups = w.cfg.get("groups") or {}
    for d in docs:
        for group in ([d.group] if d.group else []) + list(d.diagram_groups.values()):
            if group not in groups:
                warns.append(Warning("unknown-group", f"group '{group}' is not declared in wiki.config.yaml", d.path))
        for dependency in d.depends_on:
            if dependency not in by_id:
                warns.append(Warning("broken-dependency", f"unknown dependency '{dependency}'", d.path))
        for target in d.diagram_links.values():
            if target not in destinations:
                warns.append(Warning("broken-diagram-link", f"unknown diagram target '{target}'", d.path))
        warns += figure_issues(w, d, groups, destinations)
        if d.parent and d.parent not in by_id:
            warns.append(Warning("broken-parent", f"unknown parent '{d.parent}'", d.path))
        for rel in d.related:
            if rel not in by_id:
                warns.append(Warning("broken-related", f"unknown related doc '{rel}'", d.path))
        seen, cursor = set(), d.id
        while cursor in by_id:
            if cursor in seen:
                warns.append(Warning("hierarchy-cycle", f"parent cycle involving '{cursor}'", d.path))
                break
            seen.add(cursor)
            cursor = by_id[cursor].parent
    resolve_groups(docs, by_id, groups)
    for d in docs:
        for aid, a in d.anchors.items():
            if aid in anchors:
                warns.append(Warning("duplicate-anchor", f"anchor '{aid}' defined in two docs", d.path))
            anchors[aid] = a

    for d in docs:
        for decision in d.decisions:
            for aid in decision.get("anchors", []):
                if aid not in anchors:
                    warns.append(Warning("broken-decision", f"unknown decision anchor '{aid}'", d.path))

    for t in tags:
        a = anchors.get(t.anchor)
        if a is None:
            warns.append(Warning("orphan-tag", f"tag points at unknown anchor '{t.anchor}'",
                                 f"{t.file}:{t.line_start}"))
            continue
        a.impls.append(t)

    for a in anchors.values():
        if not a.impls and a.kind in ("concept", "gotcha"):
            warns.append(Warning("unimplemented", f"'{a.full_id}' has no code tagged against it", a.doc_id))

    for d in docs:
        for r in d.refs:
            table = symbols.get(r.file)
            if table is None:
                warns.append(Warning("broken-ref", f"ref file '{r.file}' not in any scanned code root", d.path))
                continue
            hit = table.get(r.symbol)
            if hit is None:
                warns.append(Warning("broken-ref", f"symbol '{r.symbol}' not found in {r.file}", d.path))
                continue
            r.resolved = True
            r.kind, r.line_start, r.line_end, r.code, r.hljs = (
                hit["kind"], hit["line_start"], hit["line_end"], hit["code"], hit["hljs"])

    owned = {}
    for d in docs:
        for f in d.owns:
            if not w.abs(f).exists():
                warns.append(Warning("missing-file", f"`owns` lists '{f}' which does not exist", d.path))
            if f in owned:
                warns.append(Warning("double-owned", f"'{f}' is owned by both {owned[f]} and {d.id}", d.path))
            owned[f] = d.id

    return warns

# @wiki:impl renderer.groups
def resolve_groups(docs, by_id, groups):
    """A page without its own group inherits the nearest declared ancestor group."""
    for d in docs:
        cursor, seen = d, set()
        while cursor is not None and cursor.id not in seen:
            seen.add(cursor.id)
            if cursor.group in groups:
                d.group_name, d.group_color = cursor.group, groups[cursor.group]["color"]
                break
            cursor = by_id.get(cursor.parent)

SVG_FORBIDDEN_RE = re.compile(r'<(?:script|iframe|embed|object)\b', re.I)
# Handlers and javascript: URLs are only dangerous as attributes; figure text may say "onboard = 1".
SVG_UNSAFE_ATTR_RE = re.compile(r'\son[a-z]+\s*=|javascript:', re.I)
SVG_ATTR = r'(?<![\w:-])%s\s*=\s*(["\'])(.*?)\1'


def _figure_text(w, figure):
    """Return (text, problem) for a wiki-root-relative SVG figure path."""
    path = w.abs(figure)
    if w.root not in path.parents:
        return None, ("invalid-figure", f"figure '{figure}' must be inside the wiki instance")
    if not path.is_file():
        return None, ("missing-figure", f"figure '{figure}' does not exist")
    text = path.read_text(encoding="utf8", errors="replace")
    tags = re.findall(r"<[A-Za-z][^<>]*>", text)
    if (not re.search(r"<svg\b", text) or SVG_FORBIDDEN_RE.search(text)
            or any(SVG_UNSAFE_ATTR_RE.search(tag) for tag in tags)):
        return None, ("invalid-figure", f"figure '{figure}' must be SVG without scripts, embeds, or event handlers")
    return text, None


# @wiki:impl renderer.figures
def figure_issues(w, doc, groups, destinations):
    """Strict checks for a page's SVG figures: location, safety, declared groups, and link targets."""
    warns = []
    for figure in doc.figures:
        text, problem = _figure_text(w, figure)
        if problem:
            warns.append(Warning(*problem, doc.path))
            continue
        for _, group in re.findall(SVG_ATTR % "data-group", text):
            if group not in groups:
                warns.append(Warning("unknown-group", f"figure '{figure}' uses undeclared group '{group}'", doc.path))
        for _, target in re.findall(SVG_ATTR % "data-link", text):
            if target not in destinations:
                warns.append(Warning("broken-figure-link", f"figure '{figure}' links to unknown '{target}'", doc.path))
    return warns


def _add_attributes(tag, classes=(), **attributes):
    """Append classes and new attributes to one start tag."""
    if classes:
        existing = re.search(SVG_ATTR % "class", tag)
        if existing:
            quote, value = existing.groups()
            tag = tag[:existing.start(2)] + " ".join([value, *classes]).strip() + tag[existing.end(2):]
        else:
            attributes["class"] = " ".join(classes)
    extra = "".join(f' {name.replace("_", "-")}="{html.escape(value, quote=True)}"'
                    for name, value in attributes.items())
    end = len(tag) - (2 if tag.endswith("/>") else 1)
    return tag[:end].rstrip() + extra + tag[end:]


# @wiki:impl renderer.figures
def inline_figure(w, figure, alt, prefix, groups, destinations):
    """Inline one project SVG: unique IDs per page, group colours, and resolved wiki links."""
    text, problem = _figure_text(w, figure)
    if problem:
        return '<p class="figure-missing">%s</p>' % html.escape(problem[1])
    text = re.sub(r"<\?xml.*?\?>|<!DOCTYPE[^>]*>|<!--.*?-->", "", text, flags=re.S).strip()
    ids = {value for _, value in re.findall(SVG_ATTR % "id", text)}
    rename = lambda name: f"{prefix}-{name}" if name in ids else name
    text = re.sub(SVG_ATTR % "id", lambda m: f'id={m.group(1)}{rename(m.group(2))}{m.group(1)}', text)
    text = re.sub(r"url\(\s*#([^)\s]+)\s*\)", lambda m: f"url(#{rename(m.group(1))})", text)
    text = re.sub(r'\b((?:xlink:)?href)\s*=\s*(["\'])#(.*?)\2',
                  lambda m: f'{m.group(1)}={m.group(2)}#{rename(m.group(3))}{m.group(2)}', text)
    text = re.sub(r'\b(aria-(?:labelledby|describedby))\s*=\s*(["\'])(.*?)\2',
                  lambda m: f'{m.group(1)}={m.group(2)}{" ".join(map(rename, m.group(3).split()))}{m.group(2)}', text)
    linked = False
    def start_tag(match):
        nonlocal linked
        tag, name = match.group(0), match.group(1)
        group = re.search(SVG_ATTR % "data-group", tag)
        if group and group.group(2) in groups:
            tag = _add_attributes(tag, ["cw-" + groups[group.group(2)]["color"]])
        link = re.search(SVG_ATTR % "data-link", tag) if name == "a" else None
        if link and link.group(2) in destinations:
            linked = True
            tag = _add_attributes(tag, ["fig-link"], href=destinations[link.group(2)]["href"])
        return tag
    text = re.sub(r"<([A-Za-z][\w:-]*)\b[^<>]*>", start_tag, text)
    if alt and not linked and not re.search(r"<svg\b[^>]*\brole\s*=", text):
        text = re.sub(r"<svg\b[^>]*>", lambda m: _add_attributes(m.group(0), role="img", aria_label=alt), text, count=1)
    return text


def code_label(doc, section_id=None):
    """A diagram node's second line: tagged declarations of a section, or a page's owned files."""
    if section_id is None:
        if not doc.owns:
            return ""
        first = doc.owns[0]
        name = posixpath.basename(first)
        if sum(posixpath.basename(f) == name for f in doc.owns) > 1:
            name = "/".join(first.split("/")[-2:])
        return name + (f" +{len(doc.owns) - 1}" if len(doc.owns) > 1 else "")
    anchor = doc.anchors.get(section_id)
    impls = list(dict.fromkeys((t.file, t.symbol, t.kind) for t in (anchor.impls if anchor else [])))
    if not impls:
        return ""
    file, symbol, kind = impls[0]
    label = posixpath.basename(file) + (f" · {symbol}{'()' if kind == 'function' else ''}" if symbol else "")
    return label + (f" +{len(impls) - 1}" if len(impls) > 1 else "")


MERMAID_PRE_RE = re.compile(r'<pre class="mermaid">(.*?)</pre>', re.S)
NODE_SHAPES = {"[[": "]]", "[(": ")]", "([": "])", "((": "))", "{{": "}}", "[": "]", "(": ")", "{": "}", ">": "]"}
SKIP_LINE_RE = re.compile(r"^\s*(?:%%|classDef\b|class\b|style\b|linkStyle\b|click\b|subgraph\b|direction\b)")


# @wiki:impl renderer.code-labels
def annotate_mermaid(source, labels):
    """Add a code line under labelled flowchart nodes; other diagram types are left unchanged."""
    lines = source.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":   # Mermaid front matter
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    header = next((line.strip() for line in lines[start:] if line.strip() and not line.strip().startswith("%%")), "")
    if not labels or not re.match(r"(flowchart|graph)\b", header):
        return source
    names = "|".join(re.escape(name) for name in sorted(labels, key=len, reverse=True))
    opener = "|".join(re.escape(o) for o in sorted(NODE_SHAPES, key=len, reverse=True))
    declaration = re.compile(rf"(?<![\w.-])({names})({opener})")
    def annotate(line):
        if SKIP_LINE_RE.match(line):
            return line
        # Search outside quoted text and |edge labels| so their words never match node IDs.
        masked = re.sub(r'"[^"]*"|\|[^|]*\|', lambda m: m.group(0)[0] + "\0" * (len(m.group(0)) - 2) + m.group(0)[-1], line)
        out, last = [], 0
        for match in declaration.finditer(masked):
            if match.start() < last:
                continue
            node, open_ = match.groups()
            close, body_start = NODE_SHAPES[open_], match.end()
            if line.startswith('"', body_start):
                end = line.find('"', body_start + 1)
                if end < 0 or not line.startswith(close, end + 1):
                    continue
                text, stop = line[body_start + 1:end], end + 1 + len(close)
            else:
                end = line.find(close, body_start)
                text, stop = (line[body_start:end], end + len(close)) if end >= 0 else ("", -1)
            if not text.strip() or text.startswith("`") or "<br" in text.lower():
                continue
            detail = re.sub(r'["<>]', "", labels[node])
            out.append(line[last:match.start()])
            out.append(f"{node}{open_}\"{text}<br/><span class='cw-code'>{detail}</span>\"{close}")
            last = stop
        return "".join(out) + line[last:]
    return "\n".join(lines[:start] + [annotate(line) for line in lines[start:]])


def annotate_diagrams(markup, labels):
    if not labels:
        return markup
    return MERMAID_PRE_RE.sub(lambda m: '<pre class="mermaid">%s</pre>' % html.escape(
        annotate_mermaid(html.unescape(m.group(1)), labels), quote=False), markup)

# --------------------------------------------------------------------------- #
# outputs
# --------------------------------------------------------------------------- #

def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()

# @wiki:impl build.index
def build_index(w: Wiki, docs: list[Doc], tags: list[Tag], symbols=None) -> dict:
    by_file: dict[str, dict] = {}
    for d in docs:
        for f in d.owns:
            by_file.setdefault(f, {"owner_doc": None, "anchors": []})["owner_doc"] = d.id
    for d in docs:
        for a in d.anchors.values():
            for t in a.impls:
                e = by_file.setdefault(t.file, {"owner_doc": None, "anchors": []})
                e["anchors"].append({
                    "id": a.full_id, "title": a.title, "kind": a.kind,
                    "role": t.role, "symbol": t.symbol, "lines": [t.line_start, t.line_end],
                    "doc": d.id, "url": f"{d.out}#{a.slug}", "lang": t.lang,
                })
        for r in d.refs:
            if r.resolved:
                e = by_file.setdefault(r.file, {"owner_doc": None, "anchors": []})
                e.setdefault("refs", []).append(
                    {"symbol": r.symbol, "doc": d.id, "lines": [r.line_start, r.line_end]})

    return {
        "schema_version": 1,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot": snapshot(w),
        "symbols": {file: {name: {k: v for k, v in data.items() if k != "code"}
                           for name, data in table.items()} for file, table in (symbols or {}).items()},
        "wiki_root": str(w.root),
        "project": w.cfg.get("project", {}),
        "groups": w.cfg.get("groups", {}),
        "docs": [{
            "id": d.id, "title": d.title, "type": d.type, "status": d.status,
            "source": d.path, "html": d.out, "tldr": d.tldr, "owns": d.owns,
            "related": d.related, "updated": d.updated,
            "depends_on": d.depends_on, "diagram_links": d.diagram_links,
            "group": d.group_name, "diagram_groups": d.diagram_groups, "figures": d.figures,
            "used_by": [other.id for other in docs if d.id in other.depends_on],
            "summary": d.summary, "parent": d.parent,
            "children": [child.id for child in docs if child.parent == d.id],
            "markdown": d.markdown, "decisions": d.decisions,
            "sections": [{k: v for k, v in section.items() if k != "body_html"} for section in d.outline],
            "anchors": [{
                "id": a.full_id, "title": a.title, "kind": a.kind,
                "text": strip_html(a.body_html),
                "markdown": next(s["body"] for s in d.outline if s["id"] == a.full_id),
                "impls": [{"role": t.role, "file": t.file, "symbol": t.symbol,
                           "kind": t.kind, "lines": [t.line_start, t.line_end],
                           "note": t.note, "lang": t.lang} for t in a.impls],
            } for a in d.anchors.values()],
            "refs": [{"file": r.file, "symbol": r.symbol,
                      "lines": [r.line_start, r.line_end], "resolved": r.resolved}
                     for r in d.refs],
        } for d in docs],
        "by_file": by_file,
    }

def diagram_destinations(docs):
    """Resolve IDs by exact lookup, including document IDs that contain dots."""
    targets = {}
    for d in docs:
        for section in d.outline:
            targets[section["id"]] = dict(href=f"{d.out}#{section['slug']}", title=section["title"],
                kind="section", document=d.id, code=code_label(d, section["id"]))
    # An exact document ID takes precedence over a colliding section ID.
    targets.update({d.id: dict(href=d.out, title=d.title, kind="component", document=d.id,
                               code=code_label(d)) for d in docs})
    return targets


# @wiki:impl renderer.navigation
def diagram_targets(doc, docs):
    """Document IDs work automatically; local slugs and explicit mappings override them."""
    destinations = diagram_destinations(docs)
    targets = {d.id: destinations[d.id] for d in docs}
    for section in doc.outline:
        targets[section["slug"]] = dict(href=f"#{section['slug']}", title=section["title"],
                                      kind="section", document=doc.id, code=code_label(doc, section["id"]))
    for node, target in doc.diagram_links.items():
        if target in destinations:
            targets[node] = destinations[target]
    return targets


# @wiki:impl renderer.groups
def diagram_styles(doc, docs, targets, groups, locale="en"):
    """A node takes the group of the page it links to; `diagram_groups` names any node explicitly."""
    by_id = {d.id: d for d in docs}
    nodes = {node: by_id[target["document"]].group_name for node, target in targets.items()
             if target.get("document") in by_id and by_id[target["document"]].group_name}
    nodes.update({node: group for node, group in doc.diagram_groups.items() if group in groups})
    # A list keeps configuration order for the legend; JSON object keys are sorted.
    return dict(nodes=nodes, groups=[dict(name=name, color=group["color"],
                label=group["label"].get(locale, group["label"]["en"])) for name, group in groups.items()])


# @wiki:impl documents.rendering
# @wiki:impl renderer.publication
def render_site(w: Wiki, docs, tags, warns, index, translations=None):
    translations = translations or {}
    locales = ["en", *sorted(translations)]
    for locale in locales:
        _render_language(w, docs, warns, index, translations.get(locale, {}), locale, locales)


def _render_language(w, canonical, warns, index, variants, locale, locales):
    docs = localized_docs(canonical, variants, locale)
    themes = w.theme_dirs
    env = Environment(loader=FileSystemLoader([str(p) for p in themes]),
                      autoescape=select_autoescape(default=True))
    from .ui_text import translate
    env.globals["tr"] = lambda text, count=None: translate(text, locale, count)
    env.filters["basename"] = lambda p: p.rsplit("/", 1)[-1]
    site = w.site_dir
    site.mkdir(parents=True, exist_ok=True)

    editor_tpl = w.cfg.get("editor_url_template", "")
    def editor_url(f, line):
        if not editor_tpl:
            return ""
        return editor_tpl.format(abs=str(w.abs(f)), file=f, line=line)

    warn_by_doc = {}
    for x in warns:
        warn_by_doc.setdefault(x.where, []).append(x)

    by_id = {d.id: d for d in docs}
    nav = []
    nav_tree = []
    visited = set()
    def visit(d, depth, siblings):
        if d.id in visited:
            return
        visited.add(d.id)
        item = dict(id=d.id, title=d.title, out=d.out, depth=depth)
        nav.append(item)
        node = dict(**item, children=[])
        siblings.append(node)
        for child in docs:
            if child.parent == d.id:
                visit(child, depth + 1, node['children'])
    roots = [d for d in docs if not d.parent or d.parent not in by_id]
    for d in sorted(roots, key=lambda d: d.type != 'manual'):
        visit(d, 0, nav_tree)
    for d in docs:
        visit(d, 0, nav_tree)
    common = dict(nav=nav, nav_tree=nav_tree, by_id=by_id, project=w.cfg.get("project", {}), docs=docs, generated=index["generated"],
                  editor_url=editor_url, severity=SEVERITY, locale=locale, html_lang=language_tag(locale),
                  page_url=lambda name: page_name(name, locale),
                  language_options=lambda name: [dict(code=code, label=language_label(code),
                      tag=language_tag(code), href=page_name(name, code)) for code in locales])

    source_paths = {d.id: d.path for d in canonical}
    page_tpl = env.get_template("page.html.j2")
    for d in docs:
        anchor_map = {a.slug: a.title for a in d.anchors.values()}
        targets = diagram_targets(d, docs)
        groups = w.cfg.get("groups") or {}
        styles = diagram_styles(d, docs, targets, groups, locale)
        labels = ({node: t["code"] for node, t in targets.items() if t.get("code")}
                  if w.cfg.get("diagram_code_labels", True) else {})
        destinations = diagram_destinations(docs)
        figure_ids = iter(range(1, 10_000))
        def place_figure(match):
            src, alt = html.unescape(match.group(1)), html.unescape(match.group(2))
            figure = posixpath.normpath(posixpath.join(posixpath.dirname(d.path), src))
            label = f' role="group" aria-label="{html.escape(alt, quote=True)}"' if alt else ""
            return '<div class="svg-figure"%s>%s</div>' % (
                label, inline_figure(w, figure, alt, f"fig{next(figure_ids)}", groups, destinations))
        ancestors, cursor, seen = [], d.parent, {d.id}
        while cursor in by_id and cursor not in seen:
            seen.add(cursor)
            ancestors.insert(0, by_id[cursor])
            cursor = by_id[cursor].parent
        d.preamble = localize_generated(localize_links(d.preamble, d, canonical, locale), locale)
        for section in d.outline:
            section["body_html"] = FIGURE_SRC_RE.sub(place_figure, annotate_diagrams(localize_generated(
                localize_links(section["body_html"], d, canonical, locale), locale), labels))
        sections_by_slug = {section["slug"]: section for section in d.outline}
        for section in d.sections:
            section.update(sections_by_slug[section["slug"]])
            for child in section["children"]:
                child.update(sections_by_slug[child["slug"]])
        for anchor in d.anchors.values():
            anchor.body_html = sections_by_slug[anchor.slug]["body_html"]
        rendered = page_tpl.render(
            doc=d, anchor_map=(json.dumps(anchor_map) if (w.wiki_dir / "_theme/page.html.j2").is_file() else anchor_map),
            diagram_targets=targets, diagram_styles=styles, ancestors=ancestors,
            used_by=[other for other in docs if d.id in other.depends_on],
            warnings=warn_by_doc.get(source_paths[d.id], []),
            review=next((r for r in index.get("reviews", {}).get("documents", []) if r["document"] == d.id), None), **common)
        (site / d.out).write_text(rendered, encoding="utf8")

    (site / page_name("index.html", locale)).write_text(env.get_template("index.html.j2").render(
        warnings=warns, index=index, **common), encoding="utf8")
    (site / page_name("files.html", locale)).write_text(env.get_template("files.html.j2").render(
        index=index, by_file=index["by_file"], **common), encoding="utf8")

    # Package defaults first; project assets override only the files they supply.
    for theme in reversed(themes) if locale == "en" else []:
        if not theme.is_dir():
            continue
        for f in theme.rglob("*"):
            if f.is_file() and not f.name.endswith(".j2"):
                dest = site / f.relative_to(theme)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)

# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

# @wiki:impl build.orchestration
def analyze(w: Wiki):
    """Read and validate current inputs without publishing or acknowledging reviews."""
    tags, symbols, warns, nfiles = scan_code(w)
    docs = []
    for p in sorted(w.wiki_dir.rglob("*.md")):
        if any(part.startswith("_") for part in p.relative_to(w.wiki_dir).parts):
            continue
        if translation_source(p) or p.name.upper() in ("TAGS.MD", "README.MD"):
            continue
        d = parse_doc(w, p, warns)
        if d:
            docs.append(d)
    warns += join(w, docs, tags, symbols)
    return docs, tags, symbols, warns, nfiles


# @wiki:impl architecture.pipeline
# @wiki:impl build.orchestration
# @wiki:impl build.publication
def run(w: Wiki, strict: bool = False, quiet: bool = False) -> tuple[int, list[Warning], dict]:
    from .review import report
    t0 = time.time()
    model = analyze(w)
    docs, tags, symbols, warns, nfiles = model
    reviews = report(w, model=model)
    for item in reviews["documents"]:
        if item["state"] != "current":
            kind = "unreviewed-doc" if item["state"] == "unreviewed" else "outdated-doc"
            warns.append(Warning(kind, item["reason"] + "; run codewiki review status", item["source"] or item["document"]))
    translations = load_translations(w, docs, warns)
    # Do not publish a broken build over the last valid site/index.
    if strict and any(SEVERITY.get(x.kind) == "error" for x in warns):
        if not quiet:
            for x in warns:
                print(f"  [{SEVERITY.get(x.kind, 'warn'):5}] {x.kind}: {x.where} {x.message}")
        return 1, warns, {}
    index = build_index(w, docs, tags, symbols)
    index["rendered_pages"] = [page_name(name, locale) for locale in ["en", *sorted(translations)]
                               for name in ["index.html", "files.html", *[d.out for d in docs]]]
    if len(index["rendered_pages"]) != len(set(index["rendered_pages"])):
        raise ValueError("localized output filename collides with a canonical document id")
    index["reviews"] = reviews
    for doc in index["docs"]:
        item = next((r for r in reviews["documents"] if r["document"] == doc["id"]), None)
        doc["review"] = {k: item[k] for k in ("state", "reason")} if item else None
    w.site_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".codewiki-build-", dir=w.site_dir.parent) as folder:
        staged = copy.copy(w)
        staged.site_dir = Path(folder)
        try:
            render_site(staged, docs, tags, warns, index, translations)
        except TemplateError as exc:
            raise ValueError(f"theme rendering failed: {exc}") from exc
        w.site_dir.mkdir(parents=True, exist_ok=True)
        for path in staged.site_dir.rglob("*"):
            if path.is_file():
                dest = w.site_dir / path.relative_to(staged.site_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                path.replace(dest)
        # Retire only pages recorded as generated by the previous build.
        if w.index_path.is_file():
            previous = json.loads(w.index_path.read_text(encoding="utf8"))
            current_pages = set(index["rendered_pages"])
            for name in previous.get("rendered_pages", [d.get("html", "") for d in previous.get("docs", [])]):
                if name and Path(name).name == name and name.endswith(".html") and name not in current_pages:
                    (w.site_dir / name).unlink(missing_ok=True)
        w.index_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=w.index_path.parent, delete=False) as output:
            json.dump(index, output, indent=2)
        Path(output.name).replace(w.index_path)

    n_impl = sum(len(a.impls) for d in docs for a in d.anchors.values())
    n_anchor = sum(len(d.anchors) for d in docs)
    order = {"error": 0, "warn": 1, "info": 2}
    warns.sort(key=lambda x: (order.get(SEVERITY.get(x.kind, "warn"), 1), x.kind, x.where))
    errors = sum(SEVERITY.get(x.kind, "warn") == "error" for x in warns)

    if not quiet:
        print(f"docs={len(docs)}  anchors={n_anchor}  tags={len(tags)}  bound={n_impl}  "
              f"files={nfiles}  {time.time() - t0:.1f}s")
        for x in warns:
            sev = SEVERITY.get(x.kind, "warn")
            print(f"  [{sev:5}] {x.kind:20} {x.where:52} {x.message}")
        if not warns:
            print("  no problems found")
        print(f"\nwrote {w.rel(w.site_dir)}/index.html and {w.rel(w.index_path)}")
    return (1 if (strict and errors) else 0), warns, index


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="codewiki build", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any error-level problem")
    ap.add_argument("--config", default=None, help="path to wiki.config.yaml (default: discover)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    w = load_wiki(args.config)
    rc, _, _ = run(w, strict=args.strict, quiet=args.quiet)
    return rc


if __name__ == "__main__":
    sys.exit(main())
