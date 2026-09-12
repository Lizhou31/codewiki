---
name: wiki-init
description: Create a project-local wiki instance using the installed CodeWiki framework.
  Use when adding a wiki to a source repository.
---

# Wiki Init

Choose the source roots from the repository layout and the user's scope.
Run `codewiki init --root <project> --code-root <source-dir> --name '<name>'`.
Repeat `--code-root` for multiple roots; source paths are relative to the project.
The framework must already be installed in the active Python environment.

Initialization creates config, starter architecture Markdown, page templates,
portable skills, and instance agent instructions; it preserves existing files.
The core and default theme stay in the installed package. Review exclusions and
read-only globs, and replace starter prose with source-grounded architecture.
Use child subsystem/component pages as detail grows.

If repository-wide agent guidance is within the user's request, add a short
reference to `codewiki/AGENTS.md` in the existing root instructions, preserving
unrelated rules. Skills are shipped in `codewiki/skills/`; use the client's
supported discovery location when installation was requested.

Run `codewiki build --strict` with the new config and inspect `codewiki query tree`.
Do not describe starter placeholders as established facts about the project.
