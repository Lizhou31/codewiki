"""Code_Wiki: markdown prose joined to source code by tree-sitter-resolved anchors.

Entry points (instance commands accept --config or discover it upward from cwd):

    python -m codewiki build  [--strict]
    python -m codewiki query  file|anchor|search|list ...
    python -m codewiki serve  [--port N]
    python -m codewiki init   --root <project> [--code-root <path> ...]
    python -m codewiki update [--source <checkout> | --installed] [--dry-run]
"""
__version__ = "0.5.0"
