---
id: manual-getting-started
type: manual
status: stable
parent: user-manual
title: Getting started
summary: Install the framework, build its example wiki, and initialize documentation in your own project.
related: [manual-reading, manual-writing, manual-configuration]
---

## TL;DR

- CodeWiki requires Python 3.10 or newer.
- Install the framework in a virtual environment, then initialize a wiki in an existing project.
- Build with `--strict` and preview the generated HTML locally.

## Install and try the example {#install}

From the CodeWiki framework repository, run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
codewiki build --strict
codewiki serve --no-open
```

Open `http://localhost:8000` in your browser. Choose **User manual** on the
Overview page for usage guides, or **CodeWiki architecture** for implementation
documentation. Stop the preview with Ctrl+C.

You can also open `codewiki/site/index.html` directly. Built pages, syntax
highlighting, and diagrams use bundled assets and work offline.

## Add a wiki to your project {#initialize}

Keep the environment containing the installed framework active. Replace the
example path and project name below with your own; the project must already exist.

```sh
codewiki init --root /path/to/project --code-root src --name 'My Project'
cd /path/to/project
codewiki build --strict
codewiki serve --no-open
```

`--code-root src` selects a directory relative to the project root. Repeat it to
include more directories, for example `--code-root src --code-root tests`.
Individual source files are also supported. Use `--dir docs/codewiki` during
initialization if you want a different instance directory.

Initialization creates:

| Path inside `codewiki/` | Purpose |
| --- | --- |
| `wiki.config.yaml` | Project name, source roots, and output settings |
| `.codewiki-manifest.json` | Package file baselines and project location for future updates; keep in Git |
| `wiki/architecture.md` | Starter page to replace with your project's explanations |
| `wiki/_templates/` | Reusable page templates |
| `wiki/TAGS.md` | Source-tag syntax and examples |
| `integrations/` | Optional shell, pre-push, and CI examples |
| `skills/` and `AGENTS.md` | Instructions for agents working with this wiki |

Initialization also creates or appends a small marked section in the project-root
`AGENTS.md`. It directs agents to read `codewiki/AGENTS.md` before working on source
code or documentation, so wiki lookup and review apply outside the wiki folder.
With `--dir docs/codewiki`, the reference is `docs/codewiki/AGENTS.md`. Existing
root instructions are preserved. Repeating init leaves the section for that
instance unchanged; keep its marker if you customize it. Re-run init on older
instances to add the root reference without overwriting their existing guide.

Portable skills still need registration in your agent client's supported discovery
location; copying them into the wiki does not automatically register them.
Claude Code users can pass `--client claude` to init: it appends the same marked
section to the project-root `CLAUDE.md` and installs the skills into `.claude/skills/`,
which Claude Code scans automatically. Customized copies there are preserved on
repeat runs, and the flag can be added to an existing instance later.

The build creates `site/` and `index.json`. Edit the Markdown inputs; rebuild to
update the HTML and query index. Repeating `init` preserves existing instance files and
does not replace your authored pages.

To upgrade an existing instance, use [Updating an existing wiki](manual-updating.html).
`codewiki update` refreshes support files; repeating `init` preserves their old copies.

## Make your first edit {#first-edit}

Open `codewiki/wiki/architecture.md`, keep its stable `id`, and replace the starter
title, summary, and text with information about your project. Run:

```sh
codewiki build --strict
codewiki query tree
```

The tree lists your page and its sections are available through `query doc <id>`.
Continue with [Writing pages](manual-writing.html) to add children or a separate
top-level manual. For a non-default location, select the config explicitly:

```sh
codewiki build --strict --config docs/codewiki/wiki.config.yaml
codewiki serve --no-open --config docs/codewiki/wiki.config.yaml
```

New pages start unreviewed. After replacing the starter and inspecting its source,
establish an explicit baseline using the [review workflow](manual-review.html).
