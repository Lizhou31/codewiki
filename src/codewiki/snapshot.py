"""Content provenance for generated indexes; no network or PR-provider dependency."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coverage_paths(w):
    """Include explicitly owned/referenced assets even without a language adapter."""
    from .documents import read_document
    from .localization import translation_source
    paths = set()
    for page in w.wiki_dir.rglob("*.md"):
        if any(part.startswith("_") for part in page.relative_to(w.wiki_dir).parts) or page.name.upper() in ("README.MD", "TAGS.MD"):
            continue
        if translation_source(page):
            continue
        try:
            fm, _, _, _ = read_document(page)
        except ValueError:
            # The page itself still participates in freshness; build reports invalid metadata.
            continue
        paths.update(w.abs(path) for path in fm.get("owns", []))
        paths.update(w.abs(ref["file"]) for ref in fm.get("refs", []))
    return paths


# @wiki:impl history.fingerprints
def input_paths(w):
    from .build import iter_source_files
    paths = {w.cfg_path}
    paths.update((w.root / "reviews").glob("*.json"))
    paths.update(p for p in coverage_paths(w) if p.is_file())
    paths.update(p for p, _, _ in iter_source_files(w, []))
    paths.update(w.wiki_dir.rglob("*.md"))
    for theme in w.theme_dirs:
        if theme.is_dir():
            paths.update(p for p in theme.rglob("*") if p.is_file())
    return sorted(paths)


def _git(path, *args):
    try:
        result = subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                                text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def snapshot(w):
    from . import __version__
    files = {}
    for path in input_paths(w):
        stat = path.stat()
        files[w.rel(path)] = dict(sha256=digest(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)
    repos = {}
    for path in [w.root, *[w.abs(root) for root in w.cfg["code_roots"]]]:
        root = _git(path if path.is_dir() else path.parent, "rev-parse", "--show-toplevel")
        if root and root not in repos:
            repos[root] = dict(root=w.rel(root), commit=_git(root, "rev-parse", "HEAD"),
                               dirty=bool(_git(root, "status", "--porcelain")))
    return dict(framework_version=__version__, inputs=files, repositories=list(repos.values()))


# @wiki:impl queries.freshness
def freshness(w, ix):
    from . import __version__
    recorded = ix.get("snapshot")
    if not recorded:
        return dict(state="unknown", changed=[], reason="legacy index; rebuild to record provenance")
    expected = recorded["inputs"]
    current = {w.rel(p): p for p in input_paths(w)}
    changed = sorted(set(current) ^ set(expected))
    for name in set(current) & set(expected):
        # Content, not checkout timestamps, determines freshness.
        if digest(current[name]) != expected[name]["sha256"]:
            changed.append(name)
    if recorded.get("framework_version") != __version__:
        changed.append("<framework version>")
    return dict(state="stale" if changed else "current", changed=sorted(changed))
