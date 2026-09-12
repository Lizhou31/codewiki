---
id: manual-writing
type: manual
status: stable
parent: user-manual
title: Writing pages
summary: Create Markdown pages, organize a manual separately from architecture, and connect explanations to source code.
related: [manual-getting-started, manual-configuration]
---

## TL;DR

- Each page needs YAML frontmatter with a unique, stable `id`.
- Use `parent: null` for a top-level section and a parent ID for its child pages.
- Build strictly and check both the HTML page and its CLI section after editing.

## Create a separate manual {#hierarchy}

Save the following as `codewiki/wiki/user-manual.md` in your project:

```markdown
---
id: user-manual
type: manual
status: stable
parent: null
title: User manual
summary: Learn how to set up and use this project.
---

## TL;DR

- Start with the setup guide.

## First steps {#first-steps}

Open [Getting started](getting-started.html).
```

Create the linked child as `codewiki/wiki/getting-started.md`:

```markdown
---
id: getting-started
type: manual
status: stable
parent: user-manual
title: Getting started
summary: Set up the project and complete a first task.
---

## TL;DR

- Follow the setup steps below.

## Setup {#setup}

Write the prerequisites, commands, and expected result here.
```

Both pages appear in the sidebar. The root gets an Overview card; its child
appears under it. The `parent` field determines nesting, independent of the file's
directory. Use `type: manual` for manual pages. Keep architecture component pages
under their existing architecture root.

## Link pages and headings {#links}

An ID such as `getting-started` produces `getting-started.html`. Link to its
explicit heading using `[Setup](getting-started.html#setup)`. Inside the same page,
use `[Setup](#setup)`. The heading above also has the CLI section ID
`getting-started.setup`.

Preserve page IDs and explicit heading slugs when renaming titles. Use `related`
for additional page links without changing the primary hierarchy:

```yaml
related: [getting-started]
```

Page IDs must be unique; `index` and `files` are reserved. Keep authored pages
outside underscore-prefixed directories such as `_templates/`, which are excluded
from page discovery. `README.md` and `TAGS.md` are reference files, not wiki pages.

## Attach source evidence {#evidence}

For an explanation tied to implementation, add an explicit heading such as
`### Dispatch {#dispatch}` in a page whose ID is `scheduler`. Place a tag directly
above the declaration in source:

```python
# @wiki:impl scheduler.dispatch
def dispatch(value):
    return value + 1
```

The parser identifies the declaration; the tag names the documentation anchor,
not the function. `impl` links implementation, `gotcha` links a documented hazard,
and `entry` marks an entry point. A user-facing procedure can stand on its own
without an implementation tag.

For source you cannot annotate, add frontmatter references instead:

```yaml
refs:
  - file: ../src/scheduler.py
    symbols: [dispatch]
```

Paths are relative to the configuration directory, not the Markdown file. Check
your instance's `wiki/TAGS.md` for language-specific examples. Source configured
under `readonly_globs` must use document-side references.

## Validate and preview {#validate}

```sh
codewiki build --strict
codewiki query doc getting-started
codewiki query section getting-started.setup
codewiki serve --no-open
```

Open the page, follow its links, and check the displayed command examples. Strict
validation checks IDs, hierarchy, declared relationships, tags, and source
references; it does not prove that prose is correct or that every ordinary
Markdown hyperlink has a valid destination.

For architecture diagrams, node IDs can target pages or local headings. Explicit
cross-page targets use `diagram_links`; see the separate
[HTML renderer guide](renderer.html#navigation) for the resolution rules.
