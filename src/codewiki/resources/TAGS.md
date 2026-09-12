# Code tag vocabulary

Tags live in ordinary comments directly above the thing they describe. The
build resolves the *symbol* from the parse tree (tree-sitter for C, Python, YAML and
devicetree; a line scanner for .conf/.mk/Kconfig/CMake/shell), so renaming a
function never breaks a link. Never write the symbol name in the tag.

## Syntax

    @wiki:<role> <anchor-id>

`<anchor-id>` is `<doc-id>.<slug>` and must match a heading anchor in a wiki
markdown file: `### Debounce {#debounce}` inside a doc whose frontmatter says
`id: p721-key-scan` defines `p721-key-scan.debounce`.

## Roles

| Role     | Means                                                           |
|----------|-----------------------------------------------------------------|
| `impl`   | This code implements the concept.                               |
| `gotcha` | This code is subject to the documented hazard. Touch with care. |
| `entry`  | Main entry point / top of the flow for this concept.            |

Start with `impl` and `gotcha`. Add roles only when you actually miss one.

## Per language

| Files | Comment form | Binds to |
|-------|--------------|----------|
| `.c` `.h` | `/* @wiki:impl x.y */` or `// @wiki:impl x.y` | next function / struct / enum / typedef / `#define` / global |
| `.py` | `# @wiki:impl x.y` | next function, class, decorated declaration, or simple assignment |
| `.yaml` `.yml` | `# @wiki:impl x.y` | next mapping key (nested keys fine) or list item |
| `.dts` `.dtsi` `.overlay` | `/* … */` or `// …` | next node (`label: name@addr`, `&ref {`) or property |
| `.conf` | `# @wiki:impl x.y` | next `CONFIG_X=…` (or `# CONFIG_X is not set`) |
| `.mk` `Makefile` | `# @wiki:impl x.y` | next assignment, rule (with recipe) or `ifeq` |
| `Kconfig` | `# @wiki:impl x.y` | next `config X` block |
| `CMakeLists.txt` `.cmake` | `# @wiki:impl x.y` | next command |
| `.sh` | `# @wiki:impl x.y` | next function or assignment |

Contiguous comments above a target may each carry tags; all bind to that
target. The target must start within two lines of the last comment, so a tag
that has nothing directly below it becomes a **file-level** link instead of
grabbing something further down.

## Examples

    /* @wiki:impl p721-key-scan.leading-edge
     * Free text after the tag line is shown under the code panel.
     */
    static void riscv_EINT_key_deb__polling_key_status(...) { ... }

    // @wiki:gotcha p721-key-remap.mask-key-bit
    #define MASK_KEY_BIT (M_KEY_BIT_DPI | M_KEY_BIT_PAIRING | M_KEY_BIT_TWHEEL_L)

    # @wiki:impl p721-build.workqueue-stack
    CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=4096

    /* @wiki:impl p721-build.sensor-node */
    motion_sensor: aimpointpro2@0 { ... };

    # @wiki:gotcha p721-build.mk-inline-comment
    AIR_KEY_DEB_LEADING_EDGE=y

## Read-only / vendor code

Do not add tags to paths listed under `readonly_globs` in `wiki.config.yaml`.
Reference them from the doc side:

    refs:
      - {file: ../AB162X/airoha/common/middleware/airoha/hid_express/src/riscv_hid_express.c,
         symbols: [hid_express_entrance]}

The build resolves those symbols through the same symbol table and reports a
`broken-ref` error if one disappears. For YAML and devicetree you may also use
the qualified path (`p721.board`, `&spim0/motion_sensor: aimpointpro2@0/cpi`)
when a bare name is ambiguous within the file.

## Clickable architecture diagrams

Mermaid node IDs matching document IDs open their pages; node IDs matching local
heading slugs open those sections. Use frontmatter for explicit cross-page targets:

```yaml
depends_on: [configuration]
diagram_links:
  engine: renderer
  parse: documents.sections
```

The first field describes authored component dependencies and creates reverse
"used by" links. The mapping binds Mermaid node names to a document ID or a full
section ID. Explicit mappings override automatic matches. The strict build rejects
unknown destinations. Use explicit heading anchors for durable section links.
A component page can contain its own diagram, progressively revealing its tagged
implementations. These fields are also available through `codewiki query doc`.
