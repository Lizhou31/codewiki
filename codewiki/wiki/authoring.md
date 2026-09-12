---
id: authoring
type: component
status: stable
parent: architecture
related: []
refs: []
title: Starting and maintaining a wiki
summary: Initialize a project-local instance, write source-grounded pages, validate
  links, and preview with the installed framework.
owns:
- ../src/codewiki/init_project.py
- ../src/codewiki/serve.py
---

## TL;DR

- Initialization creates project-owned config, starter Markdown, templates, and portable skills.
- Stable IDs and original explanations stay with the source repository.
- The local server rebuilds on input changes and reports validation failures.

## Concepts

### Scaffold only the project-owned files {#scaffold}

`codewiki init --root <project> --code-root src` creates a `codewiki/` instance.
Repeat `--code-root` for additional source roots. Initialization preserves existing
files and does not replace user customizations on an upgrade. It adds an architecture
starter only when there are no authored pages. The copied templates cover architecture,
subsystem, component, and decision documents. Replace starter text with observed facts.

### Preview the build contract {#preview}

`codewiki serve` serves generated HTML on loopback and rebuilds when watched inputs
change. Browser reload notifications and validation errors belong to the development
server; static build output stays usable without it. Restart the server if changing
the configured output directory. CLI queries work from the saved index without a server.

## Skills

The framework ships `wiki-init`, `wiki-query`, `wiki-author`, and `wiki-build` under
`src/codewiki/resources/skills/`. Initialization copies them into the instance. Each uses
the installed CLI, so it has no dependency on a Claude-specific plugin directory.
Use the relevant client's skill discovery mechanism to register these files.
Root agent instructions can reference the instance guide for project-wide behavior.

## Maintenance

Query a covered file before changing it. If behavior changes, update its explanation
in the same change. Preserve source tags when moving or renaming declarations and
use document-side references for code configured as read-only. Run a strict build,
then inspect the affected section through both the browser and CLI.

## Preview Inputs

The preview watches the instance configuration, Markdown, source roots, and theme
files. It reloads configuration before rebuilding so changed source roots are picked
up. Invalid configuration appears as a preview error until corrected.
