---
id: languages
type: component
status: stable
parent: architecture
related: []
refs: []
title: Language adapters and source binding
summary: Tree-sitter and small statement scanners resolve documentation tags into
  source declarations without storing symbol names in tags.
owns:
- ../src/codewiki/languages.py
---

## TL;DR

- C, Python, YAML, and devicetree use Tree-sitter; build/config languages use statement scanners.
- Tags bind to the next nearby declaration and preserve documentation links across symbol renames.
- Structural parsing supplies evidence, not a complete semantic model.

## Concepts

### Adapters share one target contract {#registry}

Each adapter produces comments and declaration targets, including names, kinds,
byte ranges, line ranges, and optional qualified names. The build scanner resolves
`@wiki:impl`, `@wiki:gotcha`, and `@wiki:entry` tags against those targets. A tag
without a nearby target becomes a file-level link. The source index stores declaration
metadata for queries even when a declaration has no documentation tag.

### Python makes this repository document itself {#python}

The Python adapter recognizes functions, classes, decorated declarations, and simple
assignments. Nested definitions receive qualified names such as `Wiki.rel`.
A comment above a decorator binds to the decorated declaration. The CLI adds a
file-derived prefix, so `codewiki.build.run` can be selected without loading a file.
Source retrieval includes decorators and the declaration body.

## Constraints

The C adapter is for C grammar, not a promise of complete C++ support. Make, shell,
Kconfig, CMake, and `.conf` scanners expose useful statement boundaries without
claiming full language semantics. Preprocessor conditions and runtime dispatch
still require source review. Ambiguous names should be qualified by file or scope.

## Adding a Language

Provide a scanner returning the shared `Comment` and `Target` records, register
its `LangSpec`, and map file extensions or basenames in `DEFAULT_FILE_MAP`. Add
fixtures that check actual tag binding, qualified names, and source ranges.
Projects can override file-to-language mappings through configuration.

## Binding Verification

Python fixtures cover decorated class methods, asynchronous functions, and comment
groups. The original C, YAML, devicetree, and statement-scanner fixtures remain
part of the test suite. These checks verify source ranges and actual bindings.
