---
name: wiki-author
description: Write or update project-local CodeWiki Markdown and code anchors. Use
  when documenting architecture, behavior, hazards, or maintaining explanations
  and decision history after refactoring or other code changes.
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

## Maintain explanations and decisions

After a refactoring or modification, inspect the change and affected pages. Update
inaccurate explanations, diagrams, examples, procedures, and source references to
describe the current implementation. If the explanation remains accurate, keep
it unchanged and review it; a source change alone does not require rewriting prose
or creating a page for previously undocumented code.

Also record a decision when the rationale, tradeoffs, alternatives, or compatibility
consequences will help a future reader understand or reconsider the design. Routine
changes do not each need a decision. Keep current behavior in the main explanation
and historical context in decision records; neither replaces the other.

- For a short rationale, append to the affected page's existing frontmatter
  `decisions` list, preserving earlier entries and avoiding duplicate YAML keys.
- For a substantial choice spanning components or needing detailed context, use
  the decision template to create a page with `type: decision`, an existing
  `parent`, and relevant `related` IDs. Describe the problem, before-and-after
  structure, known alternatives, consequences, and verification. Link to it from
  affected pages and update their current explanations where needed.

Each decision entry has a stable page-local `id`, required `reason`, and optional
`anchors`, `commits` (quoted strings), and `prs` (HTTP(S) URLs) lists. Anchor IDs
must resolve to existing explicit section anchors. Record only known reasons and
references; a diff alone does not establish rationale. For an existing refactoring
commit, record its SHA. When preparing code and docs together, use an available PR
URL or add the commit reference later; do not invent a SHA. Preserve earlier
decisions and explain later replacements in a new entry or page.

## Validate and review

After changing docs or tags, run `codewiki build --strict`. Inspect the affected
HTML page and query its section to check both reading interfaces. For decision
changes, also run `codewiki query history <doc-id>` on the page holding the records;
related pages do not aggregate histories. Check the rendered expandable entries
and links to any standalone decision page. CodeWiki exposes authored references;
it does not discover rationale or verify commit/PR contents automatically.

Use `codewiki review status --outdated` to find pending existing pages. After
reviewing source and explanations, record `review updated` or `review pass` with
a specific reason, following `wiki-review` when available. If the user reserves
review for another reviewer, leave it pending. Decision records do not acknowledge
reviews, and rebuilding never clears them. Include completed acknowledgments with
the source and Markdown when committing within the user's requested scope.
