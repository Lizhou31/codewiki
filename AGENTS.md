# CodeWiki framework

This is the independent Python framework. `codewiki/` is its own project-local
wiki. `../P729/` is the sibling test project with separate repository rules;
keep compatibility work there explicit.

Use `.venv/bin/codewiki` or the installed `codewiki` command. Read progressively:
`query tree`, `query doc <id>`, `query section <id>`, then `query symbol` or
`query source` for the implementation. Before changing a covered core file,
consult `query file <path>` and update affected explanations alongside behavior.

The package owns default themes, templates, and portable skills in
`src/codewiki/resources/`. Project instances own Markdown, config, and optional theme
overrides. Preserve stable document IDs and source anchor tags. V1 uses CLI and
skills; MCP and automatic Git/PR history discovery are future features.

After code or wiki changes run `.venv/bin/codewiki build --strict`. Validate
behavior changes with `.venv/bin/python -m pytest`. For packaging changes, build
a wheel and test initialization/building from an unrelated directory. Source
ranges must not be read from a stale index.

Reusable skill instructions are in `src/codewiki/resources/skills/`; each folder
contains a portable `SKILL.md` for querying, authoring, building, or initialization.
