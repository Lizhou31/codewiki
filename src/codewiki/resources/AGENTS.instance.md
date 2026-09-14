# CodeWiki instance

This project's wiki is in `{{DIR}}/`. Use the installed `codewiki` command
(or `python -m codewiki` in its Python environment).
Run commands from the project root and select `{{DIR}}/wiki.config.yaml` with
`--config` when using build, query, serve, or review, especially for custom locations.

Read progressively: `query tree` → `query doc <id>` → `query section <id>` →
`query symbol <id>` / `query source <id>`. Use `query file <path>` before editing
covered source files. Follow the returned freshness status and continuation offsets.

When changing documented behavior, update its Markdown explanation with the code.
Preserve stable page IDs and source tags; use `refs` for configured read-only paths.
Run `codewiki build --strict` after changing Markdown, tags, or config.
After source edits, run `codewiki review status --outdated` for affected existing
pages. Use `wiki-review` to inspect them and record `updated` or `pass` with a
specific reason; a build never acknowledges review. Run `codewiki review check`
before finishing and report pending pages. Keep `{{DIR}}/reviews/*.json` with the project
in Git. Uncovered source does not require creating documentation.

Reusable skills live in `{{DIR}}/skills/`; page templates and tag syntax are in
`{{DIR}}/{{WIKI_DIR}}/_templates/` and `{{DIR}}/{{WIKI_DIR}}/TAGS.md`.

Use `codewiki update --config "{{DIR}}/wiki.config.yaml"` to upgrade the framework
and refresh support files. Use `--source <framework-checkout>` for a source build,
or `--installed` to use the currently installed framework. Commit
`{{DIR}}/.codewiki-manifest.json` so future updates can recognize local changes.
Compare conflicts in `{{DIR}}/.codewiki-update/` before adopting or acknowledging
them with `--installed --keep-local <instance-relative-path>`.
