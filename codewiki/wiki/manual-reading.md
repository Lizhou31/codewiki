---
id: manual-reading
type: manual
status: stable
parent: user-manual
title: Reading and querying
summary: Navigate the wiki in a browser, search its contents, and retrieve focused documentation or source through the CLI.
related: [manual-getting-started, manual-configuration]
---

## TL;DR

- Overview shows the top-level sections; the sidebar shows their page hierarchy.
- Query progressively: tree, document, section, symbol, then source.
- Rebuild a stale index before relying on source locations.

## Browse the site {#browse}

Use **Overview** to choose a top-level section. **User manual** and **CodeWiki
architecture** are independent sections of this wiki. The sidebar's **Find a page**
field filters page titles; **On this page** jumps to headings in the open page.

Architecture diagrams can link to pages or sections. Follow a linked node or use
the ordinary links beneath the diagram. Expand the diagram for a larger view;
press Escape to close it. Expand an **Implementation** panel to read attached code.
**Open in editor** uses the project's configured editor link.

**Source index** lists files with documentation links. If you need to search prose
or source symbols instead of page titles, use the CLI search command below.

## Find a page or section {#query}

Run these examples from the framework repository after building its wiki:

```sh
codewiki query tree
codewiki query doc user-manual
codewiki query doc manual-getting-started
codewiki query section manual-getting-started.install
codewiki query search 'source roots' --limit 5
```

`tree` shows the hierarchy and summaries. `doc` gives a page summary, its
relationships, and section IDs. `section` retrieves the selected Markdown and
available source evidence. Use IDs returned by your own wiki when querying
another project.

```sh
codewiki query doc manual-writing --full --limit 40
codewiki query doc manual-writing --full --offset 40 --limit 40
codewiki query --json search 'source roots' --limit 5
```

`--full` requests original Markdown. `--limit` and `--offset` paginate items or
text lines, depending on the query; they do not specify a token budget. JSON
responses provide `next_offset` when more content is available. Follow that value
to continue reading. Limits must be between 1 and 200.

## Inspect source evidence {#source}

For this framework's own source, try:

```sh
codewiki query file src/codewiki/build.py
codewiki query symbol codewiki.build.run
codewiki query source codewiki.build.run --limit 40
```

`file` finds documentation associated with a file. `symbol` reveals declaration
metadata; `source` reads its indexed source lines. If a name is ambiguous, use the
exact ID or file-qualified name returned by the query instead of guessing.

## Keep results current {#freshness}

Queries use the saved `index.json` and check whether inputs have changed.
After editing Markdown, source, configuration, or theme files, run:

```sh
codewiki build --strict
```

A stale index may still return old documentation with a freshness warning. Source
queries reject stale locations. If the rebuild fails, fix the reported problems
before using the source ranges; see [Troubleshooting](manual-configuration.html#troubleshooting).
