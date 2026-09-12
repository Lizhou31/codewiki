---
id: build
type: component
status: stable
parent: architecture
title: Build pipeline
summary: Join explanations to source evidence, validate the graph, then publish HTML
  and a query index from one model.
owns:
- ../src/codewiki/build.py
depends_on:
- documents
- languages
- renderer
- history
related: []
diagram_links:
  config: architecture.instances
  scan: languages.registry
  parse: documents.sections
  validate: documents.validation
  index: build.index
  render: renderer.publication
  publish: build.publication
---

## Inside the pipeline

```mermaid
flowchart TB
  config["Resolve project configuration"] --> scan["Scan source · tags + symbols"]
  config --> parse["Read Markdown · pages + sections"]
  scan --> validate["Join · validate relationships"]
  parse --> validate
  validate --> index["Build query index + snapshot"]
  index --> render["Render into staging directory"]
  render --> publish["Publish site + index"]
```

This is the execution order of `codewiki build --strict`. Select a stage to read
its implementation. Scanning and parsing are drawn as separate inputs to the join;
the current Python builder executes them sequentially.

## Orchestration {#orchestration}

`run()` scans configured source roots, parses project Markdown, then joins tags to
stable anchors. It aggregates diagnostics before deciding whether publication can
proceed. With `--strict`, any error returns a failure and keeps the last good outputs.
Warnings about timestamps and informational unimplemented concepts do not block it.

The builder coordinates other components; the language adapters own syntax-specific
extraction, and the document parser owns Markdown structure. `Tag`, `Ref`, `Anchor`,
and `Doc` carry the combined model through validation and rendering.

## Query index {#index}

`build_index()` exports document summaries, parent/child relationships, dependencies,
diagram destinations, original Markdown sections, and source symbol locations. The
`by_file` view makes file-to-document lookup possible without loading every section.
Source declaration text is excluded from the symbol index; the query command reads
bounded source ranges from a verified checkout when requested.

The snapshot fingerprints inputs and records repository state. It lets queries
detect stale ranges, but does not prove an explanation is correct.

## Publication boundaries {#publication}

HTML is first rendered in a temporary directory. Template errors leave previously
published outputs intact. On success, files are copied to the site, obsolete pages
listed in the previous index are retired, and a temporary index replaces the old one.
The entire site directory is not swapped atomically: a reader during publication
can briefly see files from different builds. The preview server reloads after build.

## Where to change behavior

| Change | Entry point |
| --- | --- |
| Add a diagnostic | `join()` and the `SEVERITY` mapping |
| Export another relationship | `build_index()` and query consumers |
| Change navigation or page layout | [Renderer](renderer.html) |
| Add a source syntax | [Language adapters](languages.html) |

The strict build and framework tests cover broken references, stale ranges,
failed rendering, and retiring deleted pages.
