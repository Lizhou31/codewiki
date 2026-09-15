---
id: manual-maintaining
type: manual
status: stable
parent: user-manual
title: Maintaining documentation
summary: Keep explanations current after code changes and preserve important design reasons with commit-linked decision records.
related: [manual-writing, manual-review, history]
---

## TL;DR {#tl-dr}

- After a refactoring or modification, review the affected wiki pages and update explanations that no longer match the code.
- When the design choice is worth remembering, also record why it changed and attach the relevant commit or PR.
- Use a decision entry for a short rationale or a separate decision page for a substantial change.
- Build and inspect the result. A decision record and a successful build do not acknowledge a documentation review.

## Decide what to maintain {#rules}

The page body explains **how the code works now**. Decision records explain **why
the design changed**. Review acknowledgments record **which version of the
explanation and linked source was inspected**.

| Situation | What to do |
| --- | --- |
| A change makes an explanation, diagram, example, or source reference inaccurate | Update the affected page to match the current implementation. |
| The choice has useful rationale, tradeoffs, rejected alternatives, or compatibility consequences | Also add a decision entry or a dedicated decision page. |
| An internal refactoring leaves the explanation accurate | Review it without rewriting accurate prose; record the decision if its rationale is useful. |
| A routine change has no lasting design rationale | Update documentation where needed; a decision record is optional. |

Record choices that will help a future reader understand or reconsider the design.
A file diff shows what changed, but does not establish why. Use supplied reasons
and verified evidence; leave unknown rationale as an open question.

## Find and update affected pages {#affected-pages}

Inspect the commit or diff, then find the existing explanations:

```sh
codewiki review status --outdated
codewiki query tree
codewiki query file src/example.py
codewiki query doc example-component
```

Replace the example file and document ID with your project's values. Rebuild with
`codewiki build --strict` if queries report a stale index, before trusting source
ranges. Review current code as well as the diff. Update affected architecture,
behavior, diagrams, examples, and user procedures. Preserve stable page IDs,
explicit heading anchors, and source tags when moving or renaming declarations.

Keep the main explanation focused on the current implementation. Put historical
before-and-after details in the decision record or decision page. Unlinked source
changes do not automatically require a new wiki page.

## Append a short decision {#decision-entry}

Append an entry to the affected page's existing YAML frontmatter `decisions` list;
preserve its earlier entries. For example:

```yaml
decisions:
  - id: extract-validation
    reason: >
      Centralized validation so the CLI and build pipeline apply
      the same rules.
    anchors: [example-component.validation]
    commits: ["<full-commit-sha>"]
```

Replace the example rationale, anchor, and commit with actual values. `id` is a
stable identifier local to this page, and `reason` is required. Optional `anchors`
must name existing explicit section anchors; omit them if unnecessary. Quote
commit IDs. An optional `prs` list accepts HTTP(S) PR URLs. Do not add a second
`decisions` YAML key to a page that already has one.

## Create a substantial decision page {#decision-page}

For changes spanning components or needing detailed alternatives and consequences,
start from the instance's `wiki/_templates/decision.md` when available. Save the
new page under the configured `wiki_dir`, outside `_templates/`. For example:

```markdown
---
id: refactor-validation
type: decision
status: draft
parent: architecture
title: Centralize validation
summary: Explain the shared validation design and its tradeoffs.
related: [example-component]
decisions:
  - id: centralize-validation
    reason: Share validation rules across CLI and build entry points.
    commits: ["<full-commit-sha>"]
---

## TL;DR {#tl-dr}

Summarize the change and its purpose.

## Context {#context}

Describe the original problem and constraints.

## Changes {#changes}

Explain the before-and-after structure and any compatibility impact.

## Alternatives {#alternatives}

Record known alternatives and the reasons for the chosen approach.

## Consequences {#consequences}

Describe benefits, tradeoffs, and conditions for revisiting the choice.

## Verification {#verification}

Record the checks performed and their results.
```

Use real existing page IDs for `parent` and `related`. The parent places the page
in the sidebar hierarchy; related pages appear as links near its title. Add a link
from affected component pages to the decision page so readers can find the reason
from the current explanation. Those component pages still need any corrections
required by the new implementation.

## Read the recorded history {#presentation}

After building, entries appear below a page's main content under **Decisions and
change references**. Each entry is collapsed by default and expands to show its
reason, anchors, commits, and PR references. Entries follow the authored list order.
Commit hashes and anchor IDs display as code text; PR URLs are clickable.

A separate decision page uses the normal page layout and its own outline. The CLI
returns the decision records attached to the requested page:

```sh
codewiki query history example-component
codewiki query history refactor-validation
```

Query the page where you stored the record; `related` does not aggregate histories.
CodeWiki does not automatically discover Git/PR rationale, verify referenced
commits or PR contents, or reconstruct old versions of a page. See
[Provenance & decisions](history.html) for the distinction from build snapshots.

## Verify and save the change {#verification}

1. Run `codewiki build --strict`.
2. Inspect the affected HTML pages, decision entries, and navigation links.
3. Use `codewiki query section <page-id.section>` and `codewiki query history <page-id>` to check the CLI view.
4. Inspect the final explanation and linked source, then follow [Reviewing outdated documents](manual-review.html) to record `updated` or `pass` with a specific reason and the inspected fingerprint. Leave pages pending when review is reserved for another reviewer.
5. Rebuild after review acknowledgments and run `codewiki review check`. Pending reviews remain separate from build validation.
6. Commit the authored Markdown and any completed review records with the project's changes.

If the refactoring already has a commit, reference its SHA in a follow-up
documentation commit. When code and documentation are still being prepared
together, record the rationale now and use an available PR URL or add the code
commit reference afterward; a commit cannot contain its own final SHA. Preserve
earlier decisions when a later choice replaces them, and explain the replacement
in a new entry or page.
