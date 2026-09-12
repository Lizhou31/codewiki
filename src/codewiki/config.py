"""Locate and load wiki.config.yaml.

Resolution order:
  1. explicit --config path
  2. $CODE_WIKI_CONFIG
  3. walk upward from cwd (then from $CLAUDE_PROJECT_DIR) looking for
     wiki.config.yaml in one of CANDIDATE_DIRS

Everything in the config is relative to the directory holding the config
file; that directory is the wiki "root" for path normalisation.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_NAME = "wiki.config.yaml"
CANDIDATE_DIRS = (".", "codewiki", "code_wiki", ".codewiki", "docs/code_wiki", "wiki")

DEFAULTS = {
    "wiki_dir": "wiki",
    "site_dir": "site",
    "code_roots": [],
    "exclude_globs": [],
    "readonly_globs": [],
    "languages": {".c": "c", ".h": "c"},
    "editor_url_template": "vscode://file/{abs}:{line}",
    "max_snippet_lines": 120,
    "project": {"name": "Code Wiki", "subtitle": ""},
}

RESOURCES = Path(__file__).resolve().parent / "resources"


class ConfigNotFound(SystemExit):
    pass


def _walk_up(start: Path):
    start = start.resolve()
    yield start
    yield from start.parents


def find_config(explicit: str | os.PathLike | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            p = p / CONFIG_NAME
        if not p.is_file():
            raise ConfigNotFound(f"config not found: {p}")
        return p.resolve()
    env = os.environ.get("CODE_WIKI_CONFIG")
    if env:
        return find_config(env)
    starts = [Path.cwd()]
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        starts.append(Path(proj))
    for start in starts:
        for d in _walk_up(start):
            for sub in CANDIDATE_DIRS:
                p = d / sub / CONFIG_NAME
                if p.is_file():
                    return p.resolve()
    raise ConfigNotFound(
        f"no {CONFIG_NAME} found upward from {starts[0]}; pass --config or "
        f"set CODE_WIKI_CONFIG, or run `python -m codewiki init` to create one")


# @wiki:impl architecture.instances
class Wiki:
    """A loaded configuration plus the derived absolute paths."""

    def __init__(self, cfg_path: Path):
        self.cfg_path = Path(cfg_path).resolve()
        self.root = self.cfg_path.parent
        try:
            raw = yaml.safe_load(self.cfg_path.read_text(encoding="utf8")) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid configuration YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("wiki config must be a mapping")
        cfg = dict(DEFAULTS)
        cfg.update(raw)
        cfg["languages"] = dict(raw.get("languages") or DEFAULTS["languages"])
        for key in ("code_roots", "exclude_globs", "readonly_globs"):
            if not isinstance(cfg[key], list) or any(not isinstance(x, str) for x in cfg[key]):
                raise ValueError(f"{key} must be a list of paths/globs")
        if not isinstance(cfg["project"], dict):
            raise ValueError("project must be a mapping")
        self.cfg = cfg
        self.wiki_dir = (self.root / cfg["wiki_dir"]).resolve()
        self.site_dir = (self.root / cfg["site_dir"]).resolve()
        self.index_path = self.root / "index.json"
        if self.site_dir == self.root or self.site_dir == self.wiki_dir or self.site_dir in self.wiki_dir.parents:
            raise ValueError("site_dir must not contain or replace the wiki source directory")
        self.theme_dirs = [self.wiki_dir / "_theme", RESOURCES / "theme"]

    def rel(self, p: os.PathLike | str) -> str:
        """Path relative to the wiki root, forward slashes, one spelling."""
        return os.path.relpath(Path(p).resolve(), self.root).replace(os.sep, "/")

    def abs(self, rel: str) -> Path:
        return (self.root / rel).resolve()


def load(explicit=None) -> Wiki:
    return Wiki(find_config(explicit))
