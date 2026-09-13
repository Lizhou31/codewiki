---
id: manual-review
type: manual
status: stable
parent: user-manual
title: Reviewing outdated documents
summary: Find existing pages affected by source changes, review or update them with a reason, and enforce the same check in CI.
related: [manual-writing, manual-configuration, reviews]
---

## TL;DR

- Run `codewiki review status --outdated` to find pending pages; no build is required.
- Review the explanation and source, then record either `updated` or `pass` with a reason.
- Commit the review records alongside the project and run `codewiki review check` in CI.

## Find affected pages {#status}

```sh
codewiki review status --outdated
codewiki review status --outdated --json
```

The report scans current source and Markdown. New or existing pages without a
record are **unreviewed**. A page becomes **outdated** when its Markdown, linked
source content, or source associations change after its last review. **Current**
means those inputs match the reviewed content. Only existing documentation is
maintained; unlinked source changes create no requirement to write a new page.

Read the page, its listed changed source, and relevant Git diffs. JSON includes
previous and current hashes and coverage. A hash identifies content; it is not a
copy of old source. Use Git history when available, or review the current source
against the explanation and say so in your reason. Rebuild before trusting source
line ranges returned by the ordinary `query source` command.

## Update or pass with a reason {#resolve}

When the explanation needs changes, edit Markdown and verify it, then acknowledge:

```sh
codewiki build --strict
codewiki review updated build --reason "Explained the new content-based review stage."
```

If the page remains accurate, keep the prose unchanged:

```sh
codewiki review pass build --reason "Reviewed the internal refactor; documented behavior is unchanged."
```

Replace `build` with your page ID and provide a reason grounded in the actual
change. Both actions record the current source and document hashes. To guard
against intervening edits, pass `--expected` with the exact `fingerprint` from the
JSON status you inspected. If it no longer matches, review the new changes first.

Pass is an acknowledgment for this version, not a permanent ignore. Later changes
request review again. There is no blanket ignore switch or automatic baseline.
Establish each initial baseline by inspecting that page and its linked source.
The packaged `wiki-review` skill guides this same workflow for an AI assistant.

For an intentionally deleted page, repair its incoming links and source tags, then
use `codewiki review retire <id> --reason "..."`. Keep the retirement record in Git.

## Save reviews with the project {#history}

Acknowledgments live in `codewiki/reviews/<id>.json` by default. Commit those records
with your source and Markdown; the project's existing Git history versions all
three. Review records carry the reason, outcome, hashes, and an informational
commit ID. The generated index is separate and can always be rebuilt.

After acknowledging reviews, regenerate the site:

```sh
codewiki build --strict
codewiki review check
```

The overview and document pages show review status as of the latest build. The
review commands always inspect current files. Review records are included in index
freshness and watched by `serve`, so acknowledgments can refresh the preview.

## Add CI and local reminders {#ci}

Use the same config for both commands in a clean CI checkout:

```sh
codewiki build --strict --config codewiki/wiki.config.yaml
codewiki review check --json --config codewiki/wiki.config.yaml
```

`check` returns 0 when all pages are current, 1 for unresolved reviews, and 2 for
invalid inputs or structural/parser errors. `status` reports pending pages without
returning 1, which makes it suitable for nonblocking editor or agent reminders.
Neither command silently records a review. Configure your CI provider to require
this job before merging; enforce independent PR approval through repository policy.

`codewiki init` copies `integrations/check-docs.sh`, `integrations/pre-push`, and
`integrations/github-actions.yml`. Existing projects can rerun init with their
original root/directory arguments to add missing resources without replacing files.
Invoke the shell example with `sh`, or merge the pre-push commands into your existing
Git hook and make it executable. Activate the Python environment containing
CodeWiki first. Hooks check the working tree, so use CI for the checked revision.

The GitHub Actions example installs from a framework checkout. In a consumer
project, replace that installation step with your pinned framework wheel/package
and select the correct config. Establish reviewed baselines before enabling the
check as a required gate. Initialization does not install hooks, publish workflows,
or change branch protection for you.
