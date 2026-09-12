---
id: architecture
type: architecture
title: System architecture
status: draft
summary: Map the project responsibilities, boundaries, and entry points.
parent: null
owns: []
refs: []
related: []
depends_on: []
diagram_links: {}
decisions: []
---

## TL;DR

- Replace this starter with a source-grounded summary.
- Mark unknown behavior as unknown; do not invent design reasons.

## Mental Model

```mermaid
flowchart LR
  input[Inputs] --> core[Core responsibilities]
  core --> output[Outputs]
```

Name diagram nodes after child document IDs to make them clickable. Use
`diagram_links` to map other node names to a page or an explicit section ID.
Describe what arrows mean, and give each major component a deeper page.

## Entry Points

Describe where execution starts and how to choose a subsystem to explore.

## Concepts

### Main responsibility {#responsibility}

Explain the responsibility and link its implementation with source tags or refs.

## Gotchas

### Constraints to verify {#constraints}

Record observed constraints and the source evidence that supports them.

## Open Questions

- What still needs investigation?
