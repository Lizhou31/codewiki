"""Install the latest published framework, then refresh an existing project instance."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .config import Wiki, find_config
from .init_project import add_root_agent_guidance
from .instance_files import INCOMING, read_manifest, refresh, safe_path

PACKAGE = "codewiki-framework"


# @wiki:impl updates.release
def installer_command(source=None):
    target = PACKAGE
    if source is not None:
        source = Path(source).resolve()
        if not source.is_dir() or not (source / "pyproject.toml").is_file():
            raise ValueError("--source must point to a framework checkout containing pyproject.toml")
        target = f"{PACKAGE} @ {source.as_uri()}"
    # Keep the venv executable spelling: resolving its symlink selects base Python.
    if importlib.util.find_spec("pip") is not None:
        return [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", target]
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--python", sys.executable,
                "--upgrade-package", PACKAGE, "--reinstall-package", PACKAGE, target]
    raise ValueError("No installer available. Install pip in this Python environment or install uv, "
                     "then retry; use --installed to refresh without downloading a release.")


# @wiki:impl updates.selection
def select_project(wiki, explicit):
    manifest = read_manifest(wiki.root)
    if explicit:
        project = Path(explicit).resolve()
    elif manifest:
        project = (wiki.root / manifest["project_root"]).resolve()
    elif wiki.root.parent == Path.cwd().resolve():
        project = wiki.root.parent
    elif wiki.root.name in ("codewiki", "code_wiki", ".codewiki") and wiki.root.parent.name != "docs":
        project = wiki.root.parent
    else:
        raise ValueError("This older instance has no project-root record; pass --root <project>.")
    if project == wiki.root or project not in wiki.root.parents:
        raise ValueError("the wiki instance must be a subdirectory of --root")
    if wiki.root not in wiki.wiki_dir.parents:
        raise ValueError("update requires wiki_dir to be a subdirectory inside the wiki instance")
    safe_path(project, "AGENTS.md")
    return project


# @wiki:impl updates.release
def main(argv=None):
    parser = argparse.ArgumentParser(prog="codewiki update", description=__doc__)
    parser.add_argument("--config", help="existing wiki.config.yaml (otherwise use normal discovery)")
    parser.add_argument("--root", help="project root, needed for older instances in custom locations")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--installed", action="store_true", help="refresh with the installed framework; skip package installation")
    source.add_argument("--source", help="build/install a local framework checkout instead of a published release")
    parser.add_argument("--dry-run", action="store_true", help="show the plan without installing or writing files")
    parser.add_argument("--keep-local", action="append", default=[], metavar="PATH",
                        help="with --installed, acknowledge a kept/merged local file against the current bundle")
    args = parser.parse_args(argv)
    if args.keep_local and not args.installed:
        parser.error("use --installed with --keep-local after reviewing incoming files")
    wiki = Wiki(find_config(args.config))
    project = select_project(wiki, args.root)
    wiki_dir = wiki.wiki_dir.relative_to(wiki.root).as_posix()
    print(f"Wiki instance: {wiki.root}", flush=True)
    if not args.installed:
        command = installer_command(args.source)
        label = "Install local source" if args.source else "Install latest published release"
        print(label + ": " + shlex.join(command), flush=True)
        if args.dry_run:
            print("Then refresh this instance using the new release. Use --installed --dry-run "
                  "to preview file changes from the currently installed framework.")
            return 0
        # Fail before package mutation if the current instance has unsafe managed paths.
        refresh(wiki.root, project, wiki_dir, dry_run=True)
        with tempfile.TemporaryDirectory(prefix="codewiki-update-") as temporary:
            result = subprocess.run(command, cwd=temporary)
            if result.returncode:
                print("Framework installation failed; instance files were not refreshed.", file=sys.stderr)
                return result.returncode if result.returncode > 0 else 1
            # Import the new release in a fresh process, not the already loaded modules.
            result = subprocess.run([sys.executable, "-m", "codewiki", "update", "--installed",
                                     "--config", str(wiki.cfg_path), "--root", str(project)], cwd=temporary)
        if result.returncode:
            print("Framework installed; instance refresh needs attention. Resolve the reported "
                  "conflicts or errors, then retry with --installed.", file=sys.stderr)
        return result.returncode if result.returncode >= 0 else 1

    plan = refresh(wiki.root, project, wiki_dir, dry_run=args.dry_run, keep_local=args.keep_local)
    for name, action in plan:
        if action != "current":
            print(f"  {action}: {name}")
    if add_root_agent_guidance(project, wiki.root, dry_run=args.dry_run):
        action = "would add" if args.dry_run else "added"
        print(f"  {action} root guidance: {project / 'AGENTS.md'}")
    conflicts = sum(action == "conflict" for _, action in plan)
    prefix = "Preview" if args.dry_run else "Refreshed"
    print(f"{prefix} with CodeWiki {__version__}: {conflicts} conflict(s).")
    if conflicts:
        print(f"Local files are preserved. Incoming versions {'would be' if args.dry_run else 'are'} in "
              f"{wiki.root / INCOMING}. Compare and adopt them, then rerun with --installed.")
        print("For a reviewed customization or merge, use --installed --keep-local <instance-relative-path>.")
    if not args.dry_run:
        print("Next: codewiki build --strict --config " + shlex.quote(str(wiki.cfg_path)))
    return 1 if conflicts else 0
