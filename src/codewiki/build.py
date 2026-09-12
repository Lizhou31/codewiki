"""Code_Wiki build: markdown + code tags -> index.json + static HTML.

    python -m codewiki build            # build
    python -m codewiki build --strict   # exit non-zero on any error
    python -m codewiki build --config path/to/wiki.config.yaml
"""
from __future__ import annotations

import argparse, fnmatch, functools, html, json, re, shutil, subprocess, sys, time
import copy
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError

from .config import Wiki, load as load_wiki
from .documents import read_document
from .snapshot import snapshot
from .languages import (DEFAULT_FILE_MAP, LANGUAGES, language_for, parse_tag_comment)

HEADING_RE = re.compile(r'^(#{2,4})\s+(.*?)(?:\s*\{#([A-Za-z0-9_\-.]+)\})?\s*$')
MERMAID_RE = re.compile(r'^```mermaid\s*$')
FENCE_RE = re.compile(r'^```\s*$')
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
    "duplicate-anchor": "error", "orphan-tag": "error", "no-id": "error",
    "no-frontmatter": "error", "broken-ref": "error", "missing-file": "error",
    "double-owned": "error", "unknown-role": "error", "tag-in-readonly": "error",
    "missing-root": "error", "invalid-doc": "error", "duplicate-doc": "error",
    "broken-related": "error", "broken-parent": "error", "hierarchy-cycle": "error",
    "broken-decision": "error", "broken-dependency": "error", "broken-diagram-link": "error",
    "anchorless-heading": "warn", "stale-doc": "warn", "parse-error": "warn",
    "unimplemented": "info",
}

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _git_root(path: Path) -> Path | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return Path(out.stdout.strip())
    except Exception:
        pass
    return None


@functools.lru_cache(maxsize=None)
def file_time(abs_path: str) -> float:
    """Commit time if the file is in git, else filesystem mtime."""
    p = Path(abs_path)
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", p.name],
                             cwd=p.parent, capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip())
    except Exception:
        pass
    return p.stat().st_mtime if p.exists() else 0.0


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

MD = md_lib.Markdown(extensions=["fenced_code", "tables", "attr_list", "sane_lists"])

def render_md(text: str) -> str:
    MD.reset()
    return MD.convert(text)

def split_mermaid(lines: list[str]):
    buf, out, in_mm = [], [], False
    for line in lines:
        if not in_mm and MERMAID_RE.match(line):
            if buf: out.append(("md", buf)); buf = []
            in_mm = True
            continue
        if in_mm and FENCE_RE.match(line):
            out.append(("mermaid", buf)); buf = []
            in_mm = False
            continue
        buf.append(line)
    if buf:
        out.append(("mermaid" if in_mm else "md", buf))
    return out

# @wiki:impl renderer.markdown
def render_body(lines: list[str]) -> tuple[str, list[str]]:
    parts, mermaids = [], []
    for kind, chunk in split_mermaid(lines):
        text = "\n".join(chunk).strip("\n")
        if not text.strip():
            continue
        if kind == "mermaid":
            mermaids.append(text)
            parts.append(
                '<div class="mermaid-wrap"><pre class="mermaid">%s</pre>'
                '<p class="mermaid-hint">Follow a linked node to explore its component or implementation.</p></div>'
                % html.escape(text))
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
        summary=fm.get("summary", ""), parent=fm.get("parent"),
        markdown=raw, preamble=render_md(preamble), outline=outline,
        decisions=fm.get("decisions", []),
    )
    for r in fm.get("refs", []):
        for sym in r["symbols"]:
            doc.refs.append(Ref(file=w.rel(w.root / r["file"]), symbol=sym))
    for section in outline:
        section["body_html"], _ = render_body(section["body"].splitlines())
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
    for d in docs:
        for dependency in d.depends_on:
            if dependency not in by_id:
                warns.append(Warning("broken-dependency", f"unknown dependency '{dependency}'", d.path))
        for target in d.diagram_links.values():
            if target not in destinations:
                warns.append(Warning("broken-diagram-link", f"unknown diagram target '{target}'", d.path))
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

    for d in docs:
        doc_t = file_time(str(w.abs(d.path)))
        newer = sorted({t.file for t in tags
                        if t.anchor in d.anchors and file_time(str(w.abs(t.file))) > doc_t})
        for f in newer:
            warns.append(Warning("stale-doc", f"'{f}' changed more recently than this doc", d.path))
    return warns

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
        "docs": [{
            "id": d.id, "title": d.title, "type": d.type, "status": d.status,
            "source": d.path, "html": d.out, "tldr": d.tldr, "owns": d.owns,
            "related": d.related, "updated": d.updated,
            "depends_on": d.depends_on, "diagram_links": d.diagram_links,
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
            targets[section["id"]] = dict(href=f"{d.out}#{section['slug']}",
                title=section["title"], kind="section", document=d.id)
    # An exact document ID takes precedence over a colliding section ID.
    targets.update({d.id: dict(href=d.out, title=d.title, kind="component", document=d.id) for d in docs})
    return targets


# @wiki:impl renderer.navigation
def diagram_targets(doc, docs):
    """Document IDs work automatically; local slugs and explicit mappings override them."""
    destinations = diagram_destinations(docs)
    targets = {d.id: destinations[d.id] for d in docs}
    for section in doc.outline:
        targets[section["slug"]] = dict(href=f"#{section['slug']}", title=section["title"],
                                      kind="section", document=doc.id)
    for node, target in doc.diagram_links.items():
        if target in destinations:
            targets[node] = destinations[target]
    return targets


# @wiki:impl documents.rendering
# @wiki:impl renderer.publication
def render_site(w: Wiki, docs, tags, warns, index):
    themes = w.theme_dirs
    env = Environment(loader=FileSystemLoader([str(p) for p in themes]),
                      autoescape=select_autoescape(default=True))
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
                  editor_url=editor_url, severity=SEVERITY)

    page_tpl = env.get_template("page.html.j2")
    for d in docs:
        anchor_map = {a.slug: a.title for a in d.anchors.values()}
        targets = diagram_targets(d, docs)
        ancestors, cursor, seen = [], d.parent, {d.id}
        while cursor in by_id and cursor not in seen:
            seen.add(cursor)
            ancestors.insert(0, by_id[cursor])
            cursor = by_id[cursor].parent
        (site / d.out).write_text(page_tpl.render(
            doc=d, anchor_map=(json.dumps(anchor_map) if (w.wiki_dir / "_theme/page.html.j2").is_file() else anchor_map),
            diagram_targets=targets, ancestors=ancestors,
            used_by=[other for other in docs if d.id in other.depends_on],
            warnings=warn_by_doc.get(d.path, []), **common), encoding="utf8")

    (site / "index.html").write_text(env.get_template("index.html.j2").render(
        warnings=warns, index=index, **common), encoding="utf8")
    (site / "files.html").write_text(env.get_template("files.html.j2").render(
        index=index, by_file=index["by_file"], **common), encoding="utf8")

    # Package defaults first; project assets override only the files they supply.
    for theme in reversed(themes):
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

# @wiki:impl architecture.pipeline
# @wiki:impl build.orchestration
# @wiki:impl build.publication
def run(w: Wiki, strict: bool = False, quiet: bool = False) -> tuple[int, list[Warning], dict]:
    t0 = time.time()
    tags, symbols, warns, nfiles = scan_code(w)

    docs = []
    for p in sorted(w.wiki_dir.rglob("*.md")):
        if any(part.startswith("_") for part in p.relative_to(w.wiki_dir).parts):
            continue
        if p.name.upper() in ("TAGS.MD", "README.MD"):
            continue
        d = parse_doc(w, p, warns)
        if d:
            docs.append(d)

    warns += join(w, docs, tags, symbols)
    # Do not publish a broken build over the last valid site/index.
    if strict and any(SEVERITY.get(x.kind) == "error" for x in warns):
        if not quiet:
            for x in warns:
                print(f"  [{SEVERITY.get(x.kind, 'warn'):5}] {x.kind}: {x.where} {x.message}")
        return 1, warns, {}
    index = build_index(w, docs, tags, symbols)
    w.site_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".codewiki-build-", dir=w.site_dir.parent) as folder:
        staged = copy.copy(w)
        staged.site_dir = Path(folder)
        try:
            render_site(staged, docs, tags, warns, index)
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
            current_pages = {d.out for d in docs}
            for doc in previous.get("docs", []):
                name = doc.get("html", "")
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
