"""`python -m codewiki <build|query|serve|init> ...`"""
from __future__ import annotations

import sys

USAGE = """usage: python -m codewiki <command> [args]

commands:
  build   scan code + markdown, write index.json and site/   (--strict, --config)
  query   tree|doc|section|anchor|file|symbol|source|search|list (--json, --config)
  serve   author mode: rebuild on save, live reload            (--port, --config)
  init    scaffold a codewiki/ folder into a project          (--root, --code-root ...)
"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "build":
        from .build import main as m
    elif cmd == "query":
        from .query import main as m
    elif cmd == "serve":
        from .serve import main as m
    elif cmd == "init":
        from .init_project import main as m
    else:
        print(USAGE)
        return 2
    try:
        return int(m(rest) or 0)
    except (ValueError, OSError) as exc:
        print(f"codewiki: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
