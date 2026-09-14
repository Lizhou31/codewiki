---
id: updates
type: component
status: stable
parent: architecture
title: Instance updates
summary: Install a framework release or source build, then reconcile package support files against recorded baselines without replacing project-owned content.
owns:
- ../src/codewiki/update.py
- ../src/codewiki/instance_files.py
- ../tests/test_update.py
depends_on: [authoring]
related: [manual-updating, testing]
---

## Update flow {#flow}

An update selects an existing instance, installs the requested framework, and launches
a fresh Python process to reconcile support files from the newly installed package.
`--installed` starts directly at reconciliation. See the [updating manual](manual-updating.html)
for commands and conflict resolution.

## Release and source installation {#release}

`update.main()` uses pip through `sys.executable`, falling back to uv with `--python`
when pip is unavailable. It requests the named distribution `codewiki-framework` from
the configured index; `--source` instead creates a named direct requirement for a local
checkout containing `pyproject.toml`. The installer validates the distribution name.
It never runs Git commands or guesses a remote repository.

Installation forces replacement so a same-version source build can refresh installed
code. Pip may reinstall dependencies; uv limits forced reinstallation to CodeWiki.
Subprocesses run in a temporary working directory and receive argument lists rather
than shell strings. The fresh child runs `python -m codewiki update --installed` with
absolute config and project paths, so it imports the new implementation. Installer
failure prevents refresh; child failure is propagated. The environment and instance
are separate mutation stages, not a transaction.

## Select an existing instance {#selection}

Configuration discovery is shared with the other CLI commands. A manifest stores the
project-root path relative to the instance; legacy conventional folders infer their
parent, while ambiguous layouts require `--root`. Update requires an instance beneath
the project and a wiki directory beneath that instance. Managed paths reject symlink
components, traversal, and file/directory collisions before the refresh writes begin.

## Track package baselines {#baselines}

`init` records SHA-256 hashes of files that match the current bundled content in
`.codewiki-manifest.json`. Existing customized files are not adopted as package copies.
Repeating init retains prior baselines. A malformed or unsupported manifest fails
rather than silently resetting ownership information. The manifest is committed with
the project and records the framework version only after a complete reconciliation.

## Reconcile support files {#files}

The shared inventory contains skills, integration examples, templates, tag guidance,
and the instance agent guide. It honors configured `wiki_dir` and the project-relative
instance path. Authored pages, config, themes, review records, and generated outputs
are outside this inventory. Removed package files are not deleted from the project.

Exact matches establish the current package hash. Missing files are added. When the
local bytes match the prior package hash, the incoming file replaces them. Local
customizations are kept when the package hash has not changed. If both differ,
local content stays in place and the new copy goes under `.codewiki-update/`.
An unknown legacy file uses that same conservative conflict path.

After comparison, `--keep-local` with `--installed` explicitly acknowledges a kept or
merged local file against the new package hash. This does not overwrite local text;
a future package change can conflict again. Unresolved conflicts retain the previous
completed version, while successful individual file baselines can advance. Each file
and manifest replacement is atomic; the whole multi-file operation is not. Root agent
guidance uses the initializer's append-once helper after reconciliation. Existing
root reference sections are not rewritten. Dry runs perform no writes or installation.

## Verification {#tests}

`tests/test_update.py` uses isolated instances and alternate package resources to check
support-file upgrades, protected project content, repeated runs, customized and legacy
files, explicit merge acknowledgments, custom wiki directories, invalid manifests, and
symlink/parent-file rejection. Installer tests check interpreter selection, local-source
requirements, dry runs, failure propagation, and fresh-process dispatch without accessing
a live package index. A built-wheel smoke check separately exercises actual installation,
initialization, updates, and strict builds from an unrelated directory.
