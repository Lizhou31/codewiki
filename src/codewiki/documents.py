"""Validate frontmatter and preserve addressable, original Markdown sections."""
from __future__ import annotations

import re
from pathlib import Path
import yaml

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)(?:[ \t]+\{#([A-Za-z0-9_.-]+)\})?[ \t]*$")


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{name} must be a list of strings")


# @wiki:impl documents.frontmatter
def validate_frontmatter(fm):
    if not isinstance(fm, dict):
        raise ValueError("frontmatter must be a mapping")
    if not isinstance(fm.get("id"), str) or not ID.fullmatch(fm["id"]) or fm["id"] in ("index", "files"):
        raise ValueError("id must be a safe, nonempty identifier (index/files are reserved)")
    for key in ("title", "summary", "type", "status", "parent"):
        if key in fm and not isinstance(fm[key], str) and not (key == "parent" and fm[key] is None):
            raise ValueError(f"{key} must be a string")
    for key in ("owns", "related", "depends_on"):
        fm[key] = fm.get(key) or []
        _strings(fm[key], key)
    links = fm.setdefault("diagram_links", {})
    if not isinstance(links, dict) or any(
        not isinstance(node, str) or not ID.fullmatch(node)
        or not isinstance(target, str) or not ID.fullmatch(target)
        for node, target in links.items()
    ):
        raise ValueError("diagram_links must map node identifiers to document or section IDs")
    fm["refs"] = fm.get("refs") or []
    if not isinstance(fm["refs"], list):
        raise ValueError("refs must be a list")
    for ref in fm["refs"]:
        if not isinstance(ref, dict) or not isinstance(ref.get("file"), str):
            raise ValueError("each ref needs a file path")
        _strings(ref.get("symbols"), "ref.symbols")
    fm["decisions"] = fm.get("decisions") or []
    if not isinstance(fm["decisions"], list):
        raise ValueError("decisions must be a list")
    ids = set()
    for decision in fm["decisions"]:
        if not isinstance(decision, dict) or any(not isinstance(decision.get(k), str) or not decision[k].strip()
                                               for k in ("id", "reason")):
            raise ValueError("each decision needs a nonempty id and reason")
        if decision["id"] in ids:
            raise ValueError("duplicate decision id")
        ids.add(decision["id"])
        for key in ("anchors", "commits", "prs"):
            _strings(decision.get(key, []), f"decision.{key}")
        if any(not url.startswith(("https://", "http://")) for url in decision.get("prs", [])):
            raise ValueError("decision PRs must be HTTP(S) URLs")
    return fm


# @wiki:impl documents.sections
def read_document(path: Path):
    raw = path.read_text(encoding="utf8")
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("unterminated YAML frontmatter")
    try:
        fm = validate_frontmatter(yaml.safe_load("".join(lines[1:end])))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    outline, fence, stack = [], None, []
    for pos in range(end + 1, len(lines)):
        line = lines[pos].rstrip("\r\n")
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            run, rest = marker.groups()
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not rest.strip():
                fence = None
            continue
        if fence:
            continue
        match = HEADING.match(line)
        if not match:
            continue
        marks, title, explicit = match.groups()
        level = len(marks)
        while stack and stack[-1][0] >= level:
            stack.pop()
        ancestor = next((title for _, title in reversed(stack) if title.lower() in ("concepts", "gotchas")), "")
        kind = {"concepts": "concept", "gotchas": "gotcha"}.get(ancestor.lower(), "other")
        stack.append((level, title))
        slug = explicit or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
        outline.append(dict(id="", slug=slug, explicit=bool(explicit), title=title,
                            level=level, kind=kind, line_start=pos + 1))
    used = set()
    for section in outline:
        if section["explicit"]:
            if section["slug"] in used:
                raise ValueError(f"duplicate heading anchor '{section['slug']}'")
            used.add(section["slug"])
    for i, section in enumerate(outline):
        if not section["explicit"]:
            base, n = section["slug"], 2
            while section["slug"] in used:
                section["slug"] = f"{base}-{n}"
                n += 1
            used.add(section["slug"])
        section["id"] = f"{fm['id']}.{section['slug']}"
        stop = next((s["line_start"] - 1 for s in outline[i + 1:] if s["level"] <= section["level"]), len(lines))
        body_stop = outline[i + 1]["line_start"] - 1 if i + 1 < len(outline) else len(lines)
        section["line_end"] = stop
        section["markdown"] = "".join(lines[section["line_start"] - 1:stop])
        section["body"] = "".join(lines[section["line_start"]:body_stop])
    first = outline[0]["line_start"] - 1 if outline else len(lines)
    return fm, raw, "".join(lines[end + 1:first]), outline
