---
name: wiki-query
description: Read a CodeWiki through its document tree, summaries, original Markdown
  sections, and source symbols. Use to understand a documented codebase or find constraints
  before editing a covered file.
---

# Wiki Query

Start with `codewiki query tree`; choose a page with `codewiki query doc <id>`.
Read relevant sections using `codewiki query section <page-id.slug>`. This returns
original Markdown, implementation locations, and a continuation offset when needed.
Use `codewiki query doc <id> --full` only when the complete page is useful.

Before changing a source file, use `codewiki query file <path>` for its ownership,
hazards, and documented behavior. No coverage means no documented constraints were
found; it is not proof that the code is safe or understood.

Use `codewiki query search <term>` to locate pages, sections, or symbols.
`codewiki query symbol <qualified-name>` inspects declarations;
`codewiki query source <qualified-name>` reads just the selected declaration.
Ambiguous names need an exact ID or `<file>:<qualified-symbol>`.

All queries support `--json`. Each subcommand accepts `--limit N --offset N`;
limits apply to result items or Markdown/source lines. Read only the branches
needed for the task. Use returned section IDs rather than guessing implicit slugs.

The CLI discovers config upward from cwd. Use `--config <path>` for another
instance. If the response says stale, rebuild with `codewiki build --strict`
before relying on source ranges. If the executable is not on PATH, use the
project environment's `python -m codewiki`. The package must be installed there.
