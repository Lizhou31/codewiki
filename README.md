# CodeWiki

An independently versioned framework for architecture documentation that lives
alongside each project's source. Markdown holds explanations; source tags and
symbol references attach the implementation at build time. The same documents
serve humans through static HTML and LLMs through progressive CLI queries.

This repository documents itself in `codewiki/`.

```text
Code_Wiki/                    # Workspace, not a Git repository
├── P729/                     # Target test project (its own repository)
└── codewiki/                 # This framework repository
    ├── src/codewiki/         # Python package and shared resources
    ├── codewiki/             # The framework's own wiki instance
    │   ├── wiki.config.yaml
    │   ├── wiki/             # Authored architecture documents
    │   └── site/             # Generated HTML
    ├── tests/
    └── pyproject.toml
```

Run the commands below from the framework repository (`Code_Wiki/codewiki/`).

## Install and try

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
codewiki build --strict
codewiki serve --no-open
```

Open http://localhost:8000, or open `codewiki/site/index.html` directly.
The site works offline; Mermaid and syntax highlighting assets are bundled.

```sh
codewiki query tree
codewiki query doc architecture
codewiki query section architecture.pipeline
codewiki query symbol codewiki.build.run
codewiki query source codewiki.build.run --limit 40
codewiki query --json search parsing --limit 5
```

## Add a wiki to another project

Install this package in the environment used for that project, then run:

```sh
codewiki init --root /path/to/project --code-root src --name 'My Project'
cd /path/to/project
codewiki build --strict
```

The project gets `codewiki/wiki.config.yaml`, Markdown, reusable page templates,
portable skills, and an `AGENTS.md` inside `codewiki/`. Its core and default
theme stay in the installed package. Add a reference to `codewiki/AGENTS.md`
in your root agent instructions when you want repository-wide wiki guidance.
Load skills from `codewiki/skills/`, or copy the needed skill directories into
your client's supported skill location. Initialization preserves existing files.

Paths in configuration and frontmatter are relative to the configuration's
directory. Use `--config path/to/wiki.config.yaml` on each command when needed;
otherwise discovery walks upward from the working directory. `CODE_WIKI_CONFIG`
can select an instance explicitly. Commands also work as `python -m codewiki`.

## Documentation contract

Each page has a stable `id`, optional `parent`, short `summary`, related page
IDs, and Markdown headings. Explicit `{#slug}` headings define stable section
IDs (`page-id.slug`). The CLI exposes the document tree, summaries, section
outlines, original Markdown, code symbols, and bounded source slices. It does
not require loading the entire wiki into an LLM's context.

```c
/* @wiki:impl scheduler.dispatch */
void dispatch(void) { /* implementation */ }
```

The tag points to `### Dispatch {#dispatch}` in the page with `id: scheduler`.
Symbol names and source ranges come from the parser. Preserve the tag when
moving or renaming a declaration. Use frontmatter `refs` for code you cannot
annotate. See `src/codewiki/resources/TAGS.md` and the self-wiki for the format.

Supported parsers: C, Python, YAML, devicetree; statement scanners: shell,
Make, Kconfig, CMake, and `.conf`. Parsing is structural; it does not establish
a complete semantic call graph or infer design reasons.

## Customization and upgrades

Put optional theme overrides in `wiki/_theme/`. Individual files override the
bundled theme; no theme copy is required for a new project. Existing P721-style
instances with a complete `_theme/` continue to work. Project-specific prose,
paths, source exclusions, read-only globs, and overrides belong in the project.

The target test project is the sibling `../P729/` repository. It is outside
this framework repository. Its existing embedded tools are preserved. You can use the
new framework against it with:

```sh
codewiki build --strict --config ../P729/code_wiki/wiki.config.yaml
codewiki query --config ../P729/code_wiki/wiki.config.yaml doc p721-arch
```

## Validation and history

`codewiki build --strict` rejects invalid documents, duplicate IDs, broken
hierarchy/relationships, missing code references, and invalid tags. Query
responses report whether their index matches current inputs. Rebuild after
editing code or docs; a changed input means review is needed, not that prose
is necessarily incorrect.

Optional decision records already support reasons, anchor IDs, commit IDs,
and PR URLs. Builds record Git revision and content fingerprints. Automatic
commit/PR discovery, historical reconstruction, and an MCP server are future
work; see the self-wiki's History and decisions page.

Run `python -m pytest` for parser, build, query, scaffolding, and compatibility
tests. Vendored JavaScript licenses are retained under
`src/codewiki/resources/theme/vendor/`. This repository does not assign a new
license to the extracted framework code.
