# CodeWiki instance

This project's wiki is in `{{DIR}}/`. Use the installed `codewiki` command
(or `python -m codewiki` in its Python environment).

Read progressively: `query tree` → `query doc <id>` → `query section <id>` →
`query symbol <id>` / `query source <id>`. Use `query file <path>` before editing
covered source files. Follow the returned freshness status and continuation offsets.

When changing documented behavior, update its Markdown explanation with the code.
Preserve stable page IDs and source tags; use `refs` for configured read-only paths.
Run `codewiki build --strict` after changing Markdown, tags, or config.

Reusable skills live in `{{DIR}}/skills/`; page templates and tag syntax are in
`{{DIR}}/wiki/_templates/` and `{{DIR}}/wiki/TAGS.md`.
