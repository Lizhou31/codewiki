---
id: skills
type: component
status: stable
parent: architecture
title: LLM skills
summary: Four portable reading and authoring workflows use the CLI to explore the
  same architecture, one level at a time.
owns:
- ../src/codewiki/resources/skills/wiki-init/SKILL.md
- ../src/codewiki/resources/skills/wiki-query/SKILL.md
- ../src/codewiki/resources/skills/wiki-author/SKILL.md
- ../src/codewiki/resources/skills/wiki-build/SKILL.md
depends_on:
- queries
- authoring
related: []
diagram_links:
  init: skills.init
  query: skills.query
  author: skills.author
  check: skills.check
---

## Skill workflows

```mermaid
flowchart TB
  init["wiki-init · establish instance"] --> author["wiki-author · explain code"]
  query["wiki-query · read evidence"] --> author
  author --> check["wiki-build · validate + render"]
  check --> query
```

These arrows describe an authoring workflow, not Python imports. Skills are Markdown
instructions loaded by an LLM client; they do not run inside the renderer.

## Initialize {#init}

`wiki-init/SKILL.md` directs the tool to inspect the repository layout, choose real
source roots, run `codewiki init`, and replace starter claims with observed facts.
The initializer copies these portable skills into the project instance; register
them using the chosen client's own discovery mechanism.

## Read progressively {#query}

`wiki-query/SKILL.md` starts with the tree or a file query. It expands a document
summary, then a selected section, and only then the relevant symbols and source.
The CLI's `--json` form exposes dependencies and diagram destinations as identifiers,
so an LLM follows the same component graph without parsing rendered HTML.

```text
codewiki query tree
codewiki query doc renderer
codewiki query section renderer.navigation
codewiki query symbol codewiki.build.diagram_targets
codewiki query source codewiki.build.diagram_targets --limit 40
```

Each result reports freshness. Rebuild a stale index before trusting source ranges.
Queries paginate results; this controls items or lines rather than guaranteeing a
token budget.

## Author with evidence {#author}

`wiki-author/SKILL.md` asks authors to read source before explaining behavior,
choose stable IDs, define ownership, and bind important concepts with tags or refs.
A high-level component diagram is an authored explanation. Keep its `depends_on`
relationships and `diagram_links` in the same Markdown change as the explanation.

## Validate the result {#check}

`wiki-build/SKILL.md` runs strict validation, resolves broken links, then checks the
reading path. Source declarations and diagram destinations must agree with the
published page. A successful build verifies structure and bindings; a human or LLM
still needs to assess whether the prose accurately describes behavior.

## Integration boundary

The shipped instructions call the installed CLI. There is no MCP server in v1.
Updating packaged skills does not overwrite customized instance copies; compare
and adopt changes explicitly when maintaining an existing project.
