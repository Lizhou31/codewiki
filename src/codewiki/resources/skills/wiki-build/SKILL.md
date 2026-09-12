---
name: wiki-build
description: Build and validate a CodeWiki index and static HTML. Use after changing
  wiki Markdown, source tags, configuration, or theme overrides.
---

# Wiki Build

Run `codewiki build --strict` from the target project, or pass `--config <path>`.
Errors include invalid documents, duplicate IDs, broken parents/relationships,
cycles, missing source refs, invalid tags, and ownership conflicts. Fix their
underlying cause; do not hide errors by removing validation. A strict failure
preserves the last valid site/index, so an old page is not proof of build success.

Warnings such as code newer than documentation need review; they do not prove
that prose must change. Missing grammars appear as parse warnings; install the
project's CodeWiki dependencies before treating parser coverage as complete.

Use `codewiki serve --no-open` for rebuild-on-save and local browser preview.
The generated site also works directly from disk. The CLI's freshness metadata
records whether indexed content matches the current inputs.
