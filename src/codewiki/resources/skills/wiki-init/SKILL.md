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
portable skills, and instance agent instructions; it preserves existing instance files.
The core and default theme stay in the installed package. Review exclusions and
read-only globs, and replace starter prose with source-grounded architecture.
Use child subsystem/component pages as detail grows.

Initialization also creates or appends a marked section in the project-root
`AGENTS.md`, directing source and documentation work to the instance guide.
Existing root instructions are preserved; repeating init leaves the section for
that instance unchanged. Keep its marker when customizing the section. `--dir`
controls the referenced path. Verify the root section points to the instance guide
without adding another manual reference. Re-run init to add this integration to older instances.
Skills are shipped in `<instance>/skills/`; use the client's
supported discovery location when installation was requested.

Run `codewiki build --strict` with the new config and inspect `codewiki query tree`.
Do not describe starter placeholders as established facts about the project.

Keep `.codewiki-manifest.json` inside the instance in Git: it records the installed
support-file baselines for `codewiki update`. Use update for existing-instance
upgrades; repeated init preserves old support files rather than upgrading them.
