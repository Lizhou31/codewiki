---
id: user-manual
type: manual
status: stable
parent: null
title: User manual
summary: Install CodeWiki, create a project wiki, find documentation, and keep your pages and source references current.
---

## TL;DR

- Start with Getting started to install CodeWiki and build your first wiki.
- Use Reading and querying to navigate the HTML site or retrieve focused answers through the CLI.
- Use Maintaining documentation for code changes and decision history, and Writing pages for authoring details.

## Choose a task {#choose-a-task}

| I want to… | Guide |
| --- | --- |
| Install CodeWiki or add it to a project | [Getting started](manual-getting-started.html) |
| Upgrade an initialized project, including source builds | [Updating an existing wiki](manual-updating.html) |
| Browse pages, inspect source, or search from the command line | [Reading and querying](manual-reading.html) |
| Create a page, organize sections, or attach source evidence | [Writing pages](manual-writing.html) |
| Maintain pages after code changes and record refactoring decisions | [Maintaining documentation](manual-maintaining.html) |
| Review outdated pages, acknowledge unchanged prose, or enforce CI | [Reviewing outdated documents](manual-review.html) |
| Select an instance, change settings, or fix build errors | [Configuration and troubleshooting](manual-configuration.html) |

These guides describe everyday usage. For the framework's internal components,
open the separate [CodeWiki architecture](architecture.html) section.

## The everyday workflow {#workflow}

1. Edit Markdown in your instance's `wiki/` directory.
2. Run `codewiki build --strict` from the project directory.
3. Open the generated site or run `codewiki serve --no-open` for a live preview.
4. Use `codewiki query tree` to find a page, then query only the section you need.
5. Review affected pages with `codewiki review status`, record outcomes with reasons,
   and run `codewiki review check`. Rebuild after acknowledgments to refresh the site.

The examples use the default instance folder, `codewiki/`. If your instance has
another location, pass `--config path/to/wiki.config.yaml` to build, serve, and query.
