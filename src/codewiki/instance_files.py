"""Track package-provided instance files without taking ownership of authored content."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from . import __version__
from .config import RESOURCES

MANIFEST = ".codewiki-manifest.json"
INCOMING = ".codewiki-update"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def safe_path(base, relative):
    """Reject escapes and symlinks before reading or replacing a managed file."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"invalid managed path: {relative}")
    path = base
    for index, part in enumerate(relative.parts):
        path = path / part
        if path.is_symlink():
            raise ValueError(f"managed path is a symlink: {path}")
        if index < len(relative.parts) - 1 and path.exists() and not path.is_dir():
            raise ValueError(f"managed path parent is not a directory: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"managed path is not a file: {path}")
    return path


# @wiki:impl updates.files
def bundled_files(instance_dir, wiki_dir="wiki"):
    """Only reusable support files; never config, authored pages, themes, or reviews."""
    files = {}
    for source, destination in (("templates", f"{wiki_dir}/_templates"),
                                ("skills", "skills"), ("integrations", "integrations")):
        for path in sorted((RESOURCES / source).rglob("*")):
            if path.is_file():
                files[f"{destination}/{path.relative_to(RESOURCES / source).as_posix()}"] = path.read_bytes()
    files[f"{wiki_dir}/TAGS.md"] = (RESOURCES / "TAGS.md").read_bytes()
    guide = (RESOURCES / "AGENTS.instance.md").read_text(encoding="utf8")
    files["AGENTS.md"] = guide.replace("{{DIR}}", instance_dir).replace(
        "{{WIKI_DIR}}", wiki_dir).encode("utf8")
    return files


# @wiki:impl updates.baselines
def read_manifest(instance):
    path = safe_path(instance, MANIFEST)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"invalid update manifest: {path}") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or not isinstance(data.get("files"), dict)
            or not isinstance(data.get("project_root"), str)
            or "framework_version" not in data
            or not isinstance(data.get("framework_version"), (str, type(None)))):
        raise ValueError(f"invalid update manifest: {path}")
    for name, value in data["files"].items():
        if (not isinstance(name, str) or not isinstance(value, str) or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)):
            raise ValueError(f"invalid file baseline in {path}")
    return data


def write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    # A partial write must not destroy the previous file or manifest.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_manifest(instance, project, files, version):
    data = dict(schema_version=1, framework_version=version,
                project_root=os.path.relpath(project, instance), files=files)
    content = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf8")
    path = safe_path(instance, MANIFEST)
    if not path.exists() or path.read_bytes() != content:
        write_bytes(path, content)


# @wiki:impl updates.baselines
def record_init(instance, project, bundle):
    """Adopt exact package copies only; rerunning init must not rebase custom files."""
    old = read_manifest(instance)
    files = dict(old["files"]) if old else {}
    complete = True
    for name, content in bundle.items():
        path = safe_path(instance, name)
        if path.is_file() and path.read_bytes() == content:
            files[name] = digest(content)
        else:
            complete = False
    version = __version__ if complete else (old["framework_version"] if old else None)
    save_manifest(instance, project, files, version)


# @wiki:impl updates.files
def refresh(instance, project, wiki_dir, dry_run=False, keep_local=()):
    old = read_manifest(instance)
    baselines = dict(old["files"]) if old else {}
    bundle = bundled_files(instance.relative_to(project).as_posix(), wiki_dir)
    unknown = set(keep_local) - bundle.keys()
    if unknown:
        raise ValueError(f"--keep-local is not a managed file: {', '.join(sorted(unknown))}")
    plan = []
    for name, content in bundle.items():
        path = safe_path(instance, name)
        current = path.read_bytes() if path.exists() else None
        if name in keep_local and current is None:
            raise ValueError(f"--keep-local file does not exist: {name}")
        if current == content:
            action = "current"
        elif name in keep_local:
            action = "kept"
        elif current is None:
            action = "add"
        elif digest(content) == baselines.get(name):
            action = "customized"
        elif digest(current) == baselines.get(name):
            action = "update"
        else:
            action = "conflict"
        incoming = safe_path(instance, f"{INCOMING}/{name}")
        plan.append((name, action, path, incoming, content))
    # Validate the complete plan before writing any files.
    safe_path(instance, MANIFEST)
    if not dry_run:
        for name, action, path, incoming, content in plan:
            if action == "conflict":
                write_bytes(incoming, content)
            elif action != "customized":
                if action not in ("current", "kept"):
                    write_bytes(path, content)
                baselines[name] = digest(content)
                # Incoming copies belong to the user once created; never remove them.
        conflicts = any(action == "conflict" for _, action, *_ in plan)
        version = (old["framework_version"] if old else None) if conflicts else __version__
        save_manifest(instance, project, baselines, version)
    return [(name, action) for name, action, *_ in plan]
