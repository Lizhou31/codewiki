---
id: documents
type: component
status: stable
parent: architecture
related: []
refs: []
title: Documents, sections, and rendering
summary: Stable page and section IDs form a hierarchy that preserves original Markdown
  while linking concepts to source declarations.
owns:
- ../src/codewiki/documents.py
- ../src/codewiki/build.py
---

## TL;DR

- Frontmatter declares identity, hierarchy, ownership, related pages, and optional decisions.
- All Markdown headings are addressable; explicit slugs provide stable code anchors.
- HTML uses package defaults with per-file project overrides.

## Concepts

### Frontmatter is the shared contract {#frontmatter}

Every page requires a safe, unique `id`. `title`, `summary`, and `status` orient the
reader; `parent` chooses the primary hierarchy; `related` adds cross-links.
`owns` assigns a primary document to a source file. `refs` links untaggable source
by file and symbol. Paths are relative to the configuration directory. Existing
pages without `parent` remain top-level, and TL;DR bullets supply a missing summary.

### Sections preserve original Markdown {#sections}

The parser recognizes heading levels one through six outside backtick or tilde
fences. Each section keeps its exact Markdown, document line range, level, and
ID. Reading a section includes its nested subsections. The renderer uses only
the direct body of each heading to avoid rendering child text twice.
An explicit heading such as `### Parse {#parse}` defines `document-id.parse`;
implicit IDs are generated for browsing and should not be used as persistent tags.

### Validation joins the model {#validation}

The join checks missing anchor targets, duplicate page IDs, conflicting ownership,
unknown related pages, invalid parents, parent cycles, and broken decision anchors.
An unresolved `refs` symbol is an error. A concept without a code tag is informational;
that can be intentional for a high-level explanation or a draft page.

### Rendering uses defaults and optional overrides {#rendering}

Jinja templates, CSS, Mermaid, and syntax highlighting ship inside the package.
A project's `wiki/_theme/` overrides individual files. Existing complete themes
retain the old template data contract. New themes render the document hierarchy,
child summaries, headings, linked implementations, and decision records.
Generated files work offline. HTML is intended for trusted project documentation;
Markdown may contain raw HTML and Mermaid supports interactive links.

## Open Questions

- Broader Markdown support such as setext headings may be added when required.
- Architectural relationships are authored; the renderer does not infer a semantic call graph.

## Build Publication

Rendering completes in a temporary directory before generated files are published.
Template errors leave the existing index and site intact. A successful rebuild
removes pages recorded in the previous index when their documents were deleted.
