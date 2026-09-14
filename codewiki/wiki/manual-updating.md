---
id: manual-updating
type: manual
status: stable
parent: user-manual
title: Updating an existing wiki
summary: Upgrade the framework and refresh an initialized project's support files while preserving authored content and local customizations.
related: [manual-getting-started, manual-configuration, updates]
---

## TL;DR {#tl-dr}

From an initialized project, run:

```sh
codewiki update
codewiki build --strict
```

`update` installs the latest published `codewiki-framework` release in the Python
environment running the command, then refreshes this project's support files using
that release. It requires a release containing the update command (0.5.0 or later).
For an older installation, first install such a release or build it from source.

## Choose the framework source {#source}

| Command | Framework used to refresh the project |
| --- | --- |
| `codewiki update` | Latest published release from the configured package index |
| `codewiki update --source /path/to/codewiki` | A fresh build/install of that local framework checkout |
| `codewiki update --installed` | The framework already running, without package installation |

Use `--source` when building from source. It uses the selected checkout as it stands;
it does not fetch Git changes, switch branches, or choose a release tag. Update the
checkout yourself when you want newer source. An editable installation already
exposes checkout changes, so `--installed` is useful during development.

Release and source installation use pip in the active Python environment, or uv
with that exact Python executable when pip is unavailable. Installer configuration,
credentials, and package-index settings still apply. Dependencies are resolved by
the installer; pip's forced reinstall can reinstall dependencies too. An install
replaces an editable installation with a regular package, leaving its checkout on
disk intact. Use a separate environment if you want to retain the editable install.
There is no automatic fallback from an unavailable release to Git.

Updating a shared Python environment changes the framework available to every
project using it. Each project's copied support files need their own update run;
use `--installed` for the remaining projects after upgrading the environment once.

## Select the project and preview {#selection}

Update uses the same configuration discovery as build and query. For a custom location:

```sh
codewiki update --config docs/codewiki/wiki.config.yaml
codewiki update --installed --dry-run --config docs/codewiki/wiki.config.yaml
```

`--dry-run` never installs packages or writes files. Without `--installed`, it shows
the installation command and planned second stage, not a comparison against an
unfetched release. With `--installed`, it shows the support-file comparison against
the current framework, including conflicts.

New instances record their project root in `.codewiki-manifest.json`. Older instances
in conventional `codewiki/`, `code_wiki/`, or `.codewiki/` folders can infer the parent.
For older nested/custom layouts, supply `--root /path/to/project` along with `--config`.
The updater requires the wiki and its configured `wiki_dir` to stay inside the project
and instance respectively. It rejects symlinked managed paths rather than following them.

## What gets refreshed {#files}

The updater manages these reusable files inside the wiki instance:

- `skills/` and `integrations/` supplied by the package.
- `_templates/` and `TAGS.md` under the configured `wiki_dir`.
- The instance `AGENTS.md`, plus a missing reference section in the project's root `AGENTS.md`.

It preserves authored pages, `wiki.config.yaml`, review records, source tags, and theme
overrides. Root agent instructions retain existing content and customized reference
sections. Files removed from a newer package are retained locally. Generated site and
index files change only when you build afterward. An update never acknowledges a
documentation review or installs the optional hooks/CI examples.

Keep `.codewiki-manifest.json` in the project's Git history. It records package hashes
for managed files and the last fully reconciled framework version. An untouched copy
can be replaced automatically. A customization is retained without conflict when its
package version has not changed. New or missing support files are added.

## Resolve local changes and older instances {#conflicts}

When both the package and local content differ from the recorded package copy,
update preserves the local file and writes the incoming version under
`.codewiki-update/`, using the same relative path. Other safe updates can still finish.
Exit status 1 indicates unresolved conflicts; the manifest's completed version does
not advance until all current support files are reconciled.

Compare the files, then either copy the incoming version over the local file and run
`codewiki update --installed`, or keep/merge your customization and explicitly record
that choice:

```sh
codewiki update --installed --keep-local skills/wiki-query/SKILL.md
```

Repeat `--keep-local` for multiple reviewed files; paths are relative to the instance.
This records the current package version as considered without replacing local text.
A later package change will request comparison again. Incoming copies may be refreshed
on later conflicts; edit the actual local file when merging. Resolved comparison copies
are retained and can be removed manually after review.

Older instances have no trustworthy hashes for their original support files. Matching
files are adopted as baselines and missing files are added; differing files are offered
as conflicts instead of assumed safe to replace. This first reconciliation establishes
future automatic updates. Repeating `init` cannot substitute for this upgrade workflow.

## Verify the result {#verification}

```sh
codewiki build --strict
codewiki query tree
codewiki review check
```

Use the same `--config` for custom locations. The strict build verifies the refreshed
framework against existing pages and bindings; review check can still report pre-existing
pending reviews. Installation failure leaves the instance unrefreshed. If installation
succeeds but refresh fails, the environment already has the new framework; resolve the
reported issue and retry with `--installed`. Package installation and the multi-file
refresh are not one atomic transaction. Each individual file is replaced atomically.
