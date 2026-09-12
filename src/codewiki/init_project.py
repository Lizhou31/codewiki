"""Scaffold project-owned Markdown/config; use the installed core and default theme."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import yaml

from .config import RESOURCES


def write_if_missing(path, text):
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")
    return True


# @wiki:impl authoring.scaffold
def main(argv=None):
    ap = argparse.ArgumentParser(prog="codewiki init", description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--dir", default="codewiki")
    ap.add_argument("--code-root", action="append", default=[])
    ap.add_argument("--name")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    instance = (root / args.dir).resolve()
    if instance == root or root not in instance.parents:
        raise ValueError("--dir must be a subdirectory inside the project")
    roots = [os.path.relpath((root / path).resolve(), instance) for path in args.code_root or ["src"]]
    cfg = dict(wiki_dir="wiki", site_dir="site", code_roots=roots,
               exclude_globs=["*/build/*", "*/out/*", "*/node_modules/*", "*/.venv/*"],
               readonly_globs=[], languages={}, editor_url_template="vscode://file/{abs}:{line}",
               max_snippet_lines=120, project=dict(name=args.name or root.name, subtitle="Code Wiki"))
    made = []
    def write(path, text):
        if write_if_missing(instance / path, text):
            made.append(str(path))
    write("wiki.config.yaml", "# Paths are relative to this configuration file.\n" + yaml.safe_dump(cfg, sort_keys=False))
    write(".gitignore", "site/\n__pycache__/\n")
    for folder, destination in (("templates", "wiki/_templates"), ("skills", "skills")):
        for path in sorted((RESOURCES / folder).rglob("*")):
            if path.is_file():
                write(Path(destination) / path.relative_to(RESOURCES / folder), path.read_text(encoding="utf8"))
    write("wiki/TAGS.md", (RESOURCES / "TAGS.md").read_text(encoding="utf8"))
    write("AGENTS.md", (RESOURCES / "AGENTS.instance.md").read_text(encoding="utf8").replace("{{DIR}}", args.dir))
    # An existing instance keeps its authored entry pages and hierarchy.
    wiki_dir = instance / "wiki"
    existing_pages = [p for p in wiki_dir.rglob("*.md")
                      if not any(part.startswith("_") for part in p.relative_to(wiki_dir).parts)
                      and p.name.upper() not in ("TAGS.MD", "README.MD")]
    if not existing_pages:
        starter = (RESOURCES / "templates/architecture.md").read_text(encoding="utf8")
        write("wiki/architecture.md", starter)
    print(f"Wiki instance: {instance}")
    for path in made:
        print(f"  + {path}")
    print("Default theme and core come from the installed CodeWiki package.")
    print(f"Next: edit wiki/architecture.md; add child pages from wiki/_templates/; codewiki build --strict --config {instance / 'wiki.config.yaml'}")
    return 0
