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

The sidebar begins with **Overview**, followed by **User manual** and **CodeWiki
architecture**. Use Overview to choose a top-level section; its cards also put the
manual first. The manual and architecture are independent sections. Click the arrow beside a
parent page to expand or collapse its children; click its title to open that page.
Keyboard users can focus the arrow control and press Enter or Space. The current
page's ancestor groups open automatically. **Expand all** and **Collapse all**
control the whole tree.

Expansion choices apply to the page currently open. Navigating to another page
or reloading restores that page's initial groups. On a narrow screen, open
**Browse documentation** first to reveal the navigation.

The sidebar's **Find a page** field filters page titles and opens the groups leading
to matching pages. Clear the field or press Escape to restore the previous expanded
groups. The all-group controls are disabled while filtering. **On this page** jumps
to headings in the open page.

Title matching ignores case and requires every word you enter. A matching parent
does not reveal all its children unless they also match; clear the search to
browse the complete branch. Individual disclosure arrows remain usable without
JavaScript, while search and the all-group controls require it.

Architecture diagrams can link to pages or sections. Follow a linked node or use
the ordinary links beneath the diagram. Expand the diagram for a larger view;
press Escape to close it. Expand an **Implementation** panel to read attached code.
**Open in editor** uses the project's configured editor link.

Use **+** and **−**, or scroll over a diagram, to zoom. Drag with a mouse or one
finger to move around; **Fit** restores the whole diagram. Zoom ranges from 25%
to 800% of the fitted view. The same controls work in the expanded view, and
opening or closing it preserves your position and zoom. For keyboard navigation,
focus the diagram canvas: **+ / −** zoom, arrow keys move the view, and **0** or
**Home** fits it again. Clicking a node still follows its link; dragging does not.

**Source index** lists files with documentation links. If you need to search prose
or source symbols instead of page titles, use the CLI search command below.

The overview and individual pages also show documentation review status:
**unreviewed** means no baseline exists, **outdated** means inputs changed since
review, and **current** means reviewed content matches. These labels reflect the
latest build. See [Reviewing outdated documents](manual-review.html) for live
status and how to resolve a review.

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

## Switch the HTML language {#translations}

When translations exist, the top bar offers **English** and **繁體中文（台灣）**.
Choose a language to open the same page in that language. Navigation, page links,
and diagrams retain that language. Pages without a translation display an English
fallback notice. The switcher works offline and without JavaScript. CLI commands
and skills continue to return English regardless of the selected browser language.
