---
name: wiki-review
description: Review existing CodeWiki documents flagged by source changes or missing baselines, update explanations when necessary, and record a reason for each reviewed version. Does not require documenting uncovered source.
---

# Review existing documentation

Run `codewiki review status --outdated --json` with the project's config. This
reads current files without trusting or rebuilding a saved index. Resolve reported
structural or parser errors before recording acknowledgments.

Work one affected document at a time. Read its Markdown and the changed source
paths from `changes`; inspect its current `snapshot.coverage` and the previous
record for removed or moved bindings. `owns`, `refs`, and tags define the scope,
not every file in the repository. Use Git diff/history to inspect prior content
when available. A stored hash or commit is an identifier, not stored source text;
if the earlier source is unavailable, review the current explanation against the
current implementation and describe that limitation in the reason.

For an unreviewed page, establish its initial baseline by reading the page and
its linked source. Do not bulk-pass missing baselines or infer accuracy from a
successful build. Read current Markdown directly; rebuild before using CLI source
ranges from the saved index.

If the explanation needs changes, edit it while preserving stable page IDs and
heading anchors. Run `codewiki build --strict`, then check the relevant rendered
page and CLI section. Refresh status and inspect the final content. Record the
specific behavior corrected:

    codewiki review updated <id> --reason "..." --expected <fingerprint>

If the prose remains accurate, leave it unchanged and explain which source change
was reviewed and why it does not affect the explanation:

    codewiki review pass <id> --reason "..." --expected <fingerprint>

Use the fingerprint from the status response for the exact final content reviewed.
If it is rejected, inspect the intervening changes before retrying. A removed page
requires `codewiki review retire <id> --reason "..." --expected <fingerprint>`;
retirement is appropriate only when that removal is intentional and links/tags
have been repaired. Do not remove coverage or review records just to clear a gate.

Finish with `codewiki build --strict` and `codewiki review check`. Report remaining
pending pages accurately when only a subset was requested. Keep Markdown, source,
and `reviews/*.json` in the same project's Git history; do not commit, push, or
change CI policy unless the user's task authorizes it. Review reasons are explicit
attestations by the author/agent; repository PR policy supplies independent approval.
