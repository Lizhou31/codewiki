---
name: wiki-author
description: Write or update project-local CodeWiki Markdown and code anchors. Use
  when documenting architecture, behavior, hazards, or the reason for a code change.
---

# Wiki Author

Inspect existing coverage with `codewiki query tree`, `doc`, `section`, and `file`.
Use the instance's `wiki/_templates/` for architecture, subsystem, component, or
decision pages. Paths in frontmatter are relative to `wiki.config.yaml`.

Keep stable page IDs and explicit `{#slug}` headings. Set `parent` for the
primary hierarchy and `related` for cross-links. Start each page with a short
summary and a TL;DR; put details in addressable sections. A child page should
explain its own responsibility without requiring every sibling to be read.

Ground behavior and design reasons in source or supplied evidence. Mark unknown
reasons as open questions. Source implementations stay in source: add
`@wiki:impl <page-id.slug>` in a comment immediately above the declaration.
Use `gotcha` for a hazard or `entry` for an entry point. Preserve tags when moving
or renaming declarations. For supported comment forms and binding rules, read the
instance's `wiki/TAGS.md` as needed. Never tag configured read-only paths; use
`refs: [{file: ../src/file.c, symbols: [symbol]}]` instead.

Optional frontmatter `decisions` records contain `id`, `reason`, and optional
`anchors`, `commits` (quoted strings), and `prs` (HTTP(S) URLs) lists. Record only
known reasons and references. A changed file alone does not establish rationale.

After changing docs or tags, run `codewiki build --strict`. Inspect the affected
HTML page and query its section to check both reading interfaces. Update the
relevant explanation alongside a behavior change; a freshness warning calls
for review, not an automatic rewrite of prose.

Use `codewiki review status --outdated` to find pending existing pages. After
reviewing source and explanations, record `review updated` or `review pass` with
a specific reason, following `wiki-review` when available. Rebuilding never clears
a review; commit acknowledgments with the source and Markdown when committing.
