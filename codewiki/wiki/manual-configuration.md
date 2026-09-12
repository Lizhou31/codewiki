---
id: manual-configuration
type: manual
status: stable
parent: user-manual
title: Configuration and troubleshooting
summary: Select the right wiki instance, configure source scanning and preview, and resolve common build and query problems.
related: [manual-getting-started, manual-writing, manual-reading]
---

## TL;DR

- Configuration and frontmatter paths resolve from the directory containing `wiki.config.yaml`.
- Pass `--config` when working with multiple instances.
- A strict build reports errors and keeps the previous published output when validation fails.

## Select an instance {#select-instance}

Build, query, and serve discover configuration by walking upward from your working
directory. An explicit `--config` takes precedence over `CODE_WIKI_CONFIG`, which
takes precedence over automatic discovery.

```sh
codewiki build --strict --config /path/to/project/codewiki/wiki.config.yaml
codewiki query --config /path/to/project/codewiki/wiki.config.yaml tree
codewiki serve --config /path/to/project/codewiki/wiki.config.yaml --no-open
```

Use the same configuration for all three commands. If a command shows the wrong
project, check both your working directory and `CODE_WIKI_CONFIG`.

## Configure the project {#settings}

For the default `project/codewiki/wiki.config.yaml` layout, a typical configuration is:

```yaml
wiki_dir: wiki
site_dir: site
code_roots:
  - ../src
  - ../tests
exclude_globs:
  - '*/build/*'
  - '*/__pycache__/*'
readonly_globs:
  - '../src/vendor/*'
languages: {}
max_snippet_lines: 120
editor_url_template: 'vscode://file/{abs}:{line}'
project:
  name: My Project
  subtitle: Project documentation
```

| Setting | Use |
| --- | --- |
| `wiki_dir` | Authored Markdown directory |
| `site_dir` | Generated HTML directory; keep it separate from the inputs |
| `code_roots` | Source files or directories to scan |
| `exclude_globs` | Paths to leave out of source scanning |
| `readonly_globs` | Paths where source tags are disallowed; use document-side references |
| `languages` | File-extension overrides; an empty mapping uses built-in detection |
| `max_snippet_lines` | Maximum lines in rendered declaration snippets |
| `editor_url_template` | Editor links using absolute path and line placeholders |
| `project` | Site name and subtitle |

For a theme customization, place only the files you want to override in
`wiki/_theme/`, such as `style.css`. Other files continue to use the package's
defaults. Rebuild after changing configuration or theme files.

## Preview changes {#preview}

```sh
codewiki serve --no-open --port 8001
```

Open `http://localhost:8001`. The preview watches Markdown, source roots,
configuration, and theme files, rebuilds after changes, and notifies the browser.
Fix any displayed validation errors to resume a successful preview. Restart the
server after changing `site_dir`. The default port is 8000; `--no-open` suppresses
automatic browser launch.

## Troubleshooting {#troubleshooting}

| Symptom | Action |
| --- | --- |
| `codewiki` command is not found | Activate the environment where you installed the framework. Try `python -m codewiki --help` in that environment. |
| No `wiki.config.yaml` is found | Run from your initialized project, pass `--config`, or initialize it first. |
| A new page is absent | Check its YAML frontmatter and unique ID, move it out of underscore-prefixed folders, and rebuild. |
| A page is nested under the wrong section | Set its `parent` to the intended page ID; use `null` for a separate root. |
| A strict build reports a broken parent or related page | Correct the referenced ID or restore the missing page. |
| A source reference is broken | Check the path relative to the config directory, scanned source roots, exclusions, and symbol spelling. |
| A tag points to a missing anchor | Match `page-id.slug` to the page ID and explicit `{#slug}` heading, then rebuild. |
| An anchor is listed as unbound | Add source evidence if the section describes implementation. Pure usage guidance can remain unbound; this is informational. |
| A query reports a stale or incompatible index | Rebuild with the installed framework using the same configuration, then repeat the query. |
| HTML still shows an older version after an error | Correct the build errors and rebuild; failed strict validation preserves the last published output. |
| The preview port is already in use | Select another port with `--port`. |

Use `codewiki build --help`, `codewiki query --help`, `codewiki serve --help`, and
`codewiki init --help` for the installed command options.
