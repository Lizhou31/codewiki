"""Bounded progressive queries over the same document/source model as HTML."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load as load_wiki
from .snapshot import freshness


def load_index(w):
    if not w.index_path.is_file():
        raise ValueError("index.json missing; run codewiki build --strict")
    index = json.loads(w.index_path.read_text(encoding="utf8"))
    if index.get("schema_version") != 1:
        raise ValueError("index format is unsupported or predates progressive queries; run codewiki build --strict")
    return index


def _one(items, label):
    if not items:
        raise ValueError(f"no match for {label!r}")
    if len(items) > 1:
        raise ValueError(f"ambiguous {label!r}; use an exact ID/path: " + ", ".join(x[0] for x in items[:10]))
    return items[0][1]


def document(ix, name):
    return _one([(d["id"], d) for d in ix["docs"] if d["id"] == name], name)


def summary(d):
    return {k: d.get(k) for k in ("id", "title", "type", "status", "source", "summary", "tldr", "parent", "children", "related", "depends_on", "used_by", "diagram_links")}


def resolve_file(w, ix, name):
    files = set(ix.get("by_file", {})) | set(ix.get("symbols", {}))
    path = Path(name)
    candidates = {name.replace("\\", "/")}
    if path.is_absolute() or path.exists():
        candidates.add(w.rel(path))
    candidates.add(w.rel(w.root / path))
    exact = sorted(files & candidates)
    matches = exact or sorted(f for f in files if f.endswith("/" + name.replace("\\", "/")))
    if not matches:
        return name, None
    key = _one([(f, f) for f in matches], name)
    return key, ix.get("by_file", {}).get(key, {})


def section(ix, name):
    all_sections = [(s["id"], (d, s)) for d in ix["docs"] for s in d.get("sections", [])]
    exact = [s for s in all_sections if s[0] == name]
    return _one(exact or [s for s in all_sections if s[0].endswith("." + name)], name)


# @wiki:impl queries.symbols
def symbols(ix):
    seen = set()
    for file, table in ix.get("symbols", {}).items():
        for alias, entry in table.items():
            key = (file, entry["line_start"], entry["line_end"])
            if key in seen:
                continue
            seen.add(key)
            module = file.removesuffix(".py").replace("\\", "/").lstrip("./").replace("/", ".")
            yield dict(entry, file=file, id=module + "." + entry.get("qualified", alias))


def symbol_matches(ix, name):
    entries = list(symbols(ix))
    exact = [e for e in entries if name in (e["id"], f"{e['file']}:{e['qualified']}")]
    return exact or [e for e in entries if name in (e.get("symbol"), e.get("qualified")) or e["id"].endswith("." + name)]


def page(items, offset, limit):
    selected = items[offset:offset + limit]
    return dict(items=selected, total=len(items), offset=offset,
                next_offset=offset + len(selected) if offset + len(selected) < len(items) else None)


def text_page(text, offset, limit):
    result = page(text.splitlines(keepends=True), offset, limit)
    result["markdown"] = "".join(result.pop("items"))
    result["unit"] = "lines"
    return result


# @wiki:impl queries.disclosure
def query(w, ix, command, value=None, *, offset=0, limit=20, full=False):
    state = freshness(w, ix)
    response = dict(schema_version=1, command=command, freshness=state)
    if command in ("tree", "list"):
        docs = []
        visited = set()
        def walk(d, depth):
            if d["id"] in visited:
                return
            visited.add(d["id"])
            docs.append(dict(summary(d), depth=depth))
            for child in ix["docs"]:
                if child.get("parent") == d["id"]:
                    walk(child, depth + 1)
        known = {d["id"] for d in ix["docs"]}
        for d in ix["docs"]:
            if not d.get("parent") or d["parent"] not in known:
                walk(d, 0)
        for d in ix["docs"]:
            walk(d, 0)
        response.update(page(docs, offset, limit))
    elif command == "doc":
        d = document(ix, value)
        response["document"] = summary(d)
        if full:
            response.update(text_page(d.get("markdown", ""), offset, limit))
        else:
            response.update(page([{k: s[k] for k in ("id", "title", "level", "line_start", "line_end")}
                                  for s in d.get("sections", [])], offset, limit))
            response["next"] = "codewiki query section <section-id> (or doc <id> --full)"
    elif command in ("section", "anchor"):
        d, s = section(ix, value)
        if command == "anchor" and not s["explicit"]:
            raise ValueError("this section has no explicit code anchor; use query section")
        response.update(document=d["id"], source=d["source"], id=s["id"], title=s["title"])
        response.update(text_page(s["markdown"], offset, limit))
        anchor = next((a for a in d["anchors"] if a["id"] == s["id"]), None)
        response["implementations"] = anchor["impls"] if anchor else []
        response["next"] = "codewiki query source <file>:<symbol>"
    elif command == "file":
        name, coverage = resolve_file(w, ix, value)
        response.update(file=name, covered=bool(coverage))
        if coverage:
            owner = coverage.get("owner_doc")
            response["document"] = summary(document(ix, owner)) if owner else None
            entries = []
            for a in sorted(coverage.get("anchors", []), key=lambda a: a["kind"] != "gotcha"):
                d, s = section(ix, a["id"])
                entries.append(dict(a, markdown=s["body"]))
            entries.extend(dict(r, kind="ref") for r in coverage.get("refs", []))
            response.update(page(entries, offset, limit))
        else:
            response["message"] = "No wiki coverage. No documented constraints were found."
    elif command == "search":
        term = value.casefold()
        hits = []
        for d in ix["docs"]:
            if term in (d["id"] + " " + d["title"] + " " + d.get("summary", "")).casefold():
                hits.append(dict(id=d["id"], title=d["title"], kind="document", source=d["source"]))
            for s in d.get("sections", []):
                if term in (s["id"] + " " + s["title"] + " " + s["body"]).casefold():
                    hits.append(dict(id=s["id"], title=s["title"], kind="section", source=d["source"]))
        for entry in symbols(ix):
            if term in entry["id"].casefold():
                hits.append(dict(id=entry["id"], title=entry["qualified"], kind="symbol", source=entry["file"]))
        response.update(page(hits, offset, limit))
    elif command in ("symbol", "source"):
        matches = symbol_matches(ix, value)
        if command == "symbol":
            if not matches:
                raise ValueError(f"no symbol matching {value!r}")
            response.update(page(matches, offset, limit))
        else:
            target = _one([(e["id"], e) for e in matches], value)
            if state["state"] != "current":
                raise ValueError("source index is stale or unverified; run codewiki build --strict before reading source ranges")
            lines = w.abs(target["file"]).read_text(encoding="utf8", errors="replace").splitlines(keepends=True)
            response.update(symbol=target)
            response.update(text_page("".join(lines[target["line_start"] - 1:target["line_end"]]), offset, limit))
            response["line_start"] = target["line_start"] + offset
    elif command == "history":
        d = document(ix, value)
        response["document"] = d["id"]
        response["repositories"] = ix.get("snapshot", {}).get("repositories", [])
        response.update(page(d.get("decisions", []), offset, limit))
    return response


def render_text(result):
    lines = []
    if result["freshness"]["state"] != "current":
        lines.append(f"Index: {result['freshness']['state']}; run codewiki build --strict to refresh.\n")
    doc = result.get("document")
    if isinstance(doc, dict):
        lines.append(f"# {doc['title']} ({doc['id']})\n{doc.get('summary') or ''}")
        lines.append(f"Markdown: {doc['source']}")
        if doc.get("parent"):
            lines.append(f"Parent: {doc['parent']}")
        if doc.get("children"):
            lines.append("Children: " + ", ".join(doc["children"]))
        for key, label in (("depends_on", "Depends on"), ("used_by", "Used by")):
            if doc.get(key):
                lines.append(label + ": " + ", ".join(doc[key]))
        for node, target in (doc.get("diagram_links") or {}).items():
            lines.append(f"Diagram: {node} → {target}")
    if result.get("message"):
        lines.append(result["message"])
    if "markdown" in result:
        lines.append(result["markdown"])
    for item in result.get("items", []):
        label = item.get("title") or item.get("qualified") or item.get("symbol") or item.get("reason", "")
        lines.append("  " * item.get("depth", 0) + f"- {item.get('id', '')}  {label}")
        if item.get("summary"):
            lines.append("  " + item["summary"])
        if item.get("file"):
            lines.append(f"  {item['file']}:{item.get('line_start', item.get('lines', [''])[0])}")
        if item.get("markdown"):
            lines.append(item["markdown"])
        for key in ("anchors", "commits", "prs"):
            if item.get(key):
                lines.append(f"  {key}: {', '.join(item[key])}")
    for item in result.get("implementations", []):
        lines.append(f"Code: {item['file']}:{item['lines'][0]}–{item['lines'][1]}  {item['symbol'] or '(file)'}")
    if result.get("next_offset") is not None:
        lines.append(f"More: repeat with --offset {result['next_offset']}")
    if result.get("next"):
        lines.append(result["next"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codewiki query", description=__doc__)
    def options(parser):
        parser.add_argument("--config", default=argparse.SUPPRESS)
        parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    options(ap)
    sub = ap.add_subparsers(dest="command", required=True)
    for command in ("tree", "list", "doc", "section", "anchor", "file", "search", "symbol", "source", "history"):
        sp = sub.add_parser(command)
        options(sp)
        if command not in ("tree", "list"):
            sp.add_argument("value")
        sp.add_argument("--offset", type=int, default=0)
        sp.add_argument("--limit", type=int, default=20, help="maximum items or Markdown/source lines (1–200)")
        if command == "doc":
            sp.add_argument("--full", action="store_true", help="read original Markdown instead of a section outline")
    args = ap.parse_args(argv)
    if args.offset < 0 or not 1 <= args.limit <= 200:
        ap.error("offset must be nonnegative and limit must be between 1 and 200")
    try:
        w = load_wiki(getattr(args, "config", None))
        ix = load_index(w)
        result = query(w, ix, args.command, getattr(args, "value", None), offset=args.offset,
                       limit=args.limit, full=getattr(args, "full", False))
        print(json.dumps(result, ensure_ascii=False, indent=2) if getattr(args, "json", False) else render_text(result))
        return 0
    except (ValueError, OSError) as exc:
        if getattr(args, "json", False):
            print(json.dumps(dict(error=str(exc))))
        else:
            print(f"codewiki query: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
