"""Content-based documentation review API, independent of generated indexes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from .config import ConfigNotFound, load as load_wiki
from .documents import ID
from .snapshot import digest, _git

SCHEMA_VERSION = 1
HASH = re.compile(r"[0-9a-f]{64}\Z")


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def records_path(w):
    return w.root / "reviews"


def _validate_record(record, path):
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported review record: {path}")
    doc_id = record.get("document")
    if not isinstance(doc_id, str) or not ID.fullmatch(doc_id) or path.stem != doc_id:
        raise ValueError(f"invalid review document ID: {path}")
    if record.get("outcome") not in ("updated", "no-change", "retired"):
        raise ValueError(f"invalid review outcome: {path}")
    for key in ("reason", "reviewed_at"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"review record needs {key}: {path}")
    value = record.get("snapshot")
    if not isinstance(value, dict) or not isinstance(value.get("sources"), dict):
        raise ValueError(f"invalid review snapshot: {path}")
    if not isinstance(value.get("coverage"), list):
        raise ValueError(f"invalid review coverage: {path}")
    for entry in value["coverage"]:
        if not isinstance(entry, dict) or entry.get("kind") not in ("owns", "ref", "tag") or not isinstance(entry.get("file"), str):
            raise ValueError(f"invalid review coverage entry: {path}")
        required = {"ref": ("symbol",), "tag": ("anchor", "role")}.get(entry["kind"], ())
        if any(not isinstance(entry.get(key), str) or not entry[key] for key in required):
            raise ValueError(f"invalid review coverage entry: {path}")
    if set(value["sources"]) != {entry["file"] for entry in value["coverage"]}:
        raise ValueError(f"review sources do not match coverage: {path}")
    if record["outcome"] == "retired" and value != dict(document_path=None, document_sha256=None, sources={}, coverage=[]):
        raise ValueError(f"invalid retirement snapshot: {path}")
    for name, sha in value["sources"].items():
        if not isinstance(name, str) or not isinstance(sha, str) or not HASH.fullmatch(sha):
            raise ValueError(f"invalid review source hash: {path}")
    if record["outcome"] != "retired":
        if not isinstance(value.get("document_sha256"), str) or not HASH.fullmatch(value["document_sha256"]):
            raise ValueError(f"invalid document hash: {path}")
        if not isinstance(value.get("document_path"), str):
            raise ValueError(f"invalid document path: {path}")
    if record.get("fingerprint") != _hash(value):
        raise ValueError(f"review fingerprint does not match its snapshot: {path}")
    return record


def load_records(w):
    records = {}
    for path in sorted(records_path(w).glob("*.json")):
        record = _validate_record(json.loads(path.read_text(encoding="utf8")), path)
        records[record["document"]] = record
    return records


def _document_snapshot(w, doc, tags, hashes):
    coverage = [{"kind": "owns", "file": f} for f in doc.owns]
    coverage += [{"kind": "ref", "file": r.file, "symbol": r.symbol} for r in doc.refs]
    coverage += [{"kind": "tag", "file": t.file, "anchor": t.anchor, "role": t.role}
                 for t in tags if t.anchor in doc.anchors]
    coverage = sorted({json.dumps(c, sort_keys=True) for c in coverage})
    coverage = [json.loads(c) for c in coverage]
    paths = sorted({c["file"] for c in coverage})
    for path in paths:
        if path not in hashes:
            hashes[path] = digest(w.abs(path)) if w.abs(path).is_file() else None
    return dict(document_path=doc.path, document_sha256=digest(w.abs(doc.path)),
                sources={p: hashes[p] for p in paths}, coverage=coverage)


def _changes(previous, current):
    changes = []
    old_sources, new_sources = previous.get("sources", {}), current.get("sources", {})
    for path in sorted(set(old_sources) | set(new_sources)):
        old, new = old_sources.get(path), new_sources.get(path)
        if old != new:
            changes.append(dict(kind="source", path=path, previous=old, current=new))
    if previous.get("document_sha256") != current.get("document_sha256"):
        changes.append(dict(kind="document", path=current.get("document_path") or previous.get("document_path"),
                            previous=previous.get("document_sha256"), current=current.get("document_sha256")))
    if previous.get("coverage") != current.get("coverage"):
        changes.append(dict(kind="coverage", previous=previous.get("coverage", []), current=current.get("coverage", [])))
    if previous.get("document_path") != current.get("document_path"):
        changes.append(dict(kind="document-path", previous=previous.get("document_path"), current=current.get("document_path")))
    return changes


# @wiki:impl reviews.status
def report(w, *, model=None):
    """Return all review states from current files; never read or write index.json.

    `ok` is the CI result. Invalid structure/parser failures appear in `errors`;
    malformed records raise ValueError. `model` is an internal build optimization.
    """
    from .build import analyze, SEVERITY
    docs, tags, _, diagnostics, _ = model if model is not None else analyze(w)
    errors = [dict(kind=d.kind, where=d.where, message=d.message) for d in diagnostics
              if SEVERITY.get(d.kind) == "error" or d.kind == "parse-error"]
    records = load_records(w)
    items, hashes = [], {}
    for doc in docs:
        current = _document_snapshot(w, doc, tags, hashes)
        previous = records.pop(doc.id, None)
        changed = _changes(previous["snapshot"], current) if previous else []
        state = "unreviewed" if previous is None else "outdated" if changed or previous["outcome"] == "retired" else "current"
        items.append(dict(document=doc.id, title=doc.title, source=doc.path, state=state,
                          fingerprint=_hash(current), snapshot=current, previous=previous,
                          changes=changed, reason="No review baseline" if previous is None else
                          "Changed since last review" if state == "outdated" else "Reviewed content matches"))
    # A removed page is an explicit retirement, not an invisible auto-pass.
    for doc_id, previous in records.items():
        if previous["outcome"] == "retired":
            continue
        current = dict(document_path=None, document_sha256=None, sources={}, coverage=[])
        items.append(dict(document=doc_id, title=doc_id, source=previous["snapshot"].get("document_path"),
                          state="outdated", removed=True, fingerprint=_hash(current), snapshot=current,
                          previous=previous, changes=_changes(previous["snapshot"], current),
                          reason="Document removed; acknowledge retirement"))
    items.sort(key=lambda item: item["document"])
    pending = sum(item["state"] != "current" for item in items)
    return dict(schema_version=SCHEMA_VERSION, ok=not errors and not pending,
                pending=pending, total=len(items), errors=errors, documents=items)


# @wiki:impl reviews.acknowledge
def acknowledge(w, document, *, outcome, reason, expected=None):
    """Record a reviewed version and reason. Optional expected guards stale review work."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("a nonempty review reason is required")
    if outcome not in ("updated", "no-change", "retired"):
        raise ValueError("outcome must be updated, no-change, or retired")
    state = report(w)
    if state["errors"]:
        raise ValueError("fix structural/parse errors before acknowledging reviews: " +
                         "; ".join(e["message"] for e in state["errors"]))
    item = next((d for d in state["documents"] if d["document"] == document), None)
    if item is None:
        raise ValueError(f"unknown review document: {document}")
    if expected is not None and expected != item["fingerprint"]:
        raise ValueError("review inputs changed; inspect the new status before acknowledging")
    if bool(item.get("removed")) != (outcome == "retired"):
        raise ValueError("use retire only for a removed document, and pass/updated for an existing document")
    previous = item["previous"]
    if outcome == "updated" and previous and previous["snapshot"].get("document_sha256") == item["snapshot"]["document_sha256"]:
        raise ValueError("document is unchanged; use pass with a reason instead")
    record = dict(schema_version=SCHEMA_VERSION, document=document, outcome=outcome,
                  reason=reason.strip(), reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  commit=_git(w.root, "rev-parse", "HEAD"), fingerprint=item["fingerprint"], snapshot=item["snapshot"])
    folder = records_path(w)
    folder.mkdir(parents=True, exist_ok=True)
    # One file per page reduces conflicts. Git preserves previous acknowledgments.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=folder, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        temporary.replace(folder / f"{document}.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return record


def render_text(result):
    lines = [f"Documentation review: {result['pending']} pending / {result['total']} documents"]
    for error in result["errors"]:
        lines.append(f"ERROR {error['where']}: {error['message']}")
    for item in result["documents"]:
        lines.append(f"{item['state'].upper()} {item['document']}: {item['reason']}")
        for change in item["changes"]:
            lines.append(f"  {change['kind']}: {change.get('path') or 'documentation mapping'}")
    if result["pending"]:
        lines.append("Review the source and page, then use codewiki review pass|updated <id> --reason '...'.")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="codewiki review", description=__doc__)
    def options(parser):
        parser.add_argument("--config", default=argparse.SUPPRESS)
        parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    options(ap)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("status", "check", "pass", "updated", "retire"):
        parser = sub.add_parser(name)
        options(parser)
        if name in ("status", "check"):
            parser.add_argument("--outdated", action="store_true", help="show only pending reviews, including unreviewed pages")
        else:
            parser.add_argument("document")
            parser.add_argument("--reason", required=True)
            parser.add_argument("--expected", help="fingerprint from the status response you reviewed")
    args = ap.parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        w = load_wiki(getattr(args, "config", None))
        if args.command in ("status", "check"):
            result = report(w)
            if args.outdated:
                result["documents"] = [d for d in result["documents"] if d["state"] != "current"]
            print(json.dumps(result, indent=2, ensure_ascii=False) if as_json else render_text(result))
            return 2 if result["errors"] else int(args.command == "check" and not result["ok"])
        outcome = {"pass": "no-change", "updated": "updated", "retire": "retired"}[args.command]
        result = acknowledge(w, args.document, outcome=outcome, reason=args.reason, expected=args.expected)
        print(json.dumps(result, indent=2, ensure_ascii=False) if as_json else f"Reviewed {args.document}: {outcome}. Rebuild to refresh the site.")
        return 0
    except (ValueError, OSError, ConfigNotFound) as exc:
        if as_json:
            print(json.dumps(dict(schema_version=SCHEMA_VERSION, ok=False, error=str(exc))))
        else:
            print(f"codewiki review: {exc}", file=sys.stderr)
        return 2
