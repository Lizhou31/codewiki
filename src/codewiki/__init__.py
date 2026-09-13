"""Code_Wiki: markdown prose joined to source code by tree-sitter-resolved anchors.

Entry points (all accept --config, or discover wiki.config.yaml upward from cwd):

    python -m codewiki build  [--strict]
    python -m codewiki query  file|anchor|search|list ...
    python -m codewiki serve  [--port N]
    python -m codewiki init   --root <project> [--code-root <path> ...]
"""
__version__ = "0.4.0"
