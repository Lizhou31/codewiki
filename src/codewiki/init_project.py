"""Scaffold project-owned Markdown/config; use the installed core and default theme."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import yaml

from .config import RESOURCES
from .instance_files import bundled_files, read_manifest, record_init

# Agent clients with their own project-root guide file and skill discovery directory.
# The generic `AGENTS.md` reference is always written; these are opt-in via --client.
CLIENTS = {
    "claude": dict(title="Claude Code", guide="CLAUDE.md", skills=".claude/skills"),
}


def write_if_missing(path, text):
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")
    return True


# @wiki:impl authoring.scaffold
def add_root_agent_guidance(root, instance, filename="AGENTS.md", skills_dir=None, dry_run=False):
    """Append one instance reference, preserving existing instructions byte-for-byte."""
    guide = (instance.relative_to(root) / "AGENTS.md").as_posix()
    marker = f"<!-- codewiki:agent-guide {guide} -->"
    path = root / filename
    existing = path.read_bytes() if path.exists() else b""
    if marker.encode("utf8") in existing.splitlines():
        return False
    if dry_run:
        return True
    separator = b"" if not existing else (b"\n" if existing.endswith(b"\n") else b"\n\n")
    skills = f"Use the `wiki-*` skills installed in `{skills_dir}/` for those steps.\n" if skills_dir else ""
    section = (
        f"{marker}\n"
        f"## CodeWiki ({instance.relative_to(root).as_posix()})\n\n"
        f"Before working on this project's source code or documentation, read `{guide}`\n"
        "and follow its documentation lookup, maintenance, and review workflow.\n"
        "Paths in that guide are relative to the project root unless stated otherwise.\n"
        f"{skills}"
        "<!-- /codewiki:agent-guide -->\n"
    )
    with path.open("ab") as stream:
        stream.write(separator + section.encode("utf8"))
    return True


# @wiki:impl authoring.scaffold
def install_client_skills(root, skills_dir):
    """Copy the packaged skills into a client's discovery directory, keeping customized copies."""
    made = []
    for path in sorted((RESOURCES / "skills").rglob("*")):
        if path.is_file():
            target = root / skills_dir / path.relative_to(RESOURCES / "skills")
            if write_if_missing(target, path.read_text(encoding="utf8")):
                made.append(target.relative_to(root).as_posix())
    return made


# @wiki:impl authoring.scaffold
def main(argv=None):
    ap = argparse.ArgumentParser(prog="codewiki init", description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--dir", default="codewiki")
    ap.add_argument("--code-root", action="append", default=[])
    ap.add_argument("--name")
    ap.add_argument("--client", action="append", default=[], choices=sorted(CLIENTS),
                    help="also integrate an agent client's own guide file and skill directory "
                         "(repeatable; claude: CLAUDE.md and .claude/skills/)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    instance = (root / args.dir).resolve()
    if instance == root or root not in instance.parents:
        raise ValueError("--dir must be a subdirectory inside the project")
    read_manifest(instance)
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
    bundle = bundled_files(instance.relative_to(root).as_posix())
    for name, content in bundle.items():
        write(name, content.decode("utf8"))
    # An existing instance keeps its authored entry pages and hierarchy.
    wiki_dir = instance / "wiki"
    existing_pages = [p for p in wiki_dir.rglob("*.md")
                      if not any(part.startswith("_") for part in p.relative_to(wiki_dir).parts)
                      and p.name.upper() not in ("TAGS.MD", "README.MD")]
    if not existing_pages:
        starter = (RESOURCES / "templates/architecture.md").read_text(encoding="utf8")
        write("wiki/architecture.md", starter)
    root_guidance_added = add_root_agent_guidance(root, instance)
    record_init(instance, root, bundle)
    # Client-specific integration: the client's own guide file plus its skill discovery directory.
    clients = []
    for name in dict.fromkeys(args.client):
        client = CLIENTS[name]
        skills = install_client_skills(root, client["skills"])
        added = add_root_agent_guidance(root, instance, client["guide"], client["skills"])
        clients.append((client, skills, added))
    print(f"Wiki instance: {instance}")
    for path in made:
        print(f"  + {path}")
    if root_guidance_added:
        print(f"Added CodeWiki guidance to: {root / 'AGENTS.md'}")
    for client, skills, added in clients:
        if skills:
            print(f"{client['title']} skills: {root / client['skills']}")
            for path in skills:
                print(f"  + {path}")
        if added:
            print(f"Added CodeWiki guidance to: {root / client['guide']}")
    print("Default theme and core come from the installed CodeWiki package.")
    print(f"Next: edit wiki/architecture.md; add child pages from wiki/_templates/; codewiki build --strict --config {instance / 'wiki.config.yaml'}")
    return 0
