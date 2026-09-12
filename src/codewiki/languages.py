"""Language registry: how each file type is parsed and how a `@wiki:` tag
finds the thing it describes.

Two families:

* Tree-sitter languages (c, yaml, devicetree). The grammar gives us comment
  nodes and "target" nodes (declarations, mapping pairs, dts nodes/properties).
  A tag comment binds to the next target after it. Symbol names are read from
  the parse tree, so renaming never breaks a link.

* Line languages (conf, make, kconfig, cmake, shell). No grammar; a `#`
  comment line binds to the next non-blank, non-comment statement. Good enough
  for Kconfig fragments, feature .mk files and CMake lists, which are what an
  embedded project actually configures behaviour with.

Adding a language = one entry in LANGUAGES. The scanner in build.py only sees
the `Comment`/`Target` records produced here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

# --------------------------------------------------------------------------- #
# records handed to the scanner
# --------------------------------------------------------------------------- #

@dataclass
class Target:
    kind: str                 # function | type | macro | variable | node | property | key | item | statement | other
    symbol: str | None        # bare name, what a human calls it
    qualified: str | None     # path-qualified name for the symbol table (yaml a.b.c, dts &spi/node/prop)
    start_byte: int
    end_byte: int
    line_start: int           # 1-based
    line_end: int
    toplevel: bool = True     # eligible for doc-side `refs:` lookup by bare name


@dataclass
class Comment:
    text: str
    start_byte: int
    end_byte: int
    line_start: int
    line_end: int
    target: Target | None = None   # bound by the language


@dataclass
class LangSpec:
    name: str
    hljs: str                                          # highlight.js class
    scan: Callable[[bytes], tuple[list[Comment], list[Target]]]
    comment_strip: str = "/*#"                         # chars stripped from comment line edges


# --------------------------------------------------------------------------- #
# tree-sitter family
# --------------------------------------------------------------------------- #

_PARSERS: dict[str, object] = {}


def _parser(name: str):
    """Lazy import so a missing grammar only fails when that language is used."""
    if name in _PARSERS:
        return _PARSERS[name]
    from tree_sitter import Language, Parser
    if name == "c":
        import tree_sitter_c as m
    elif name == "yaml":
        import tree_sitter_yaml as m
    elif name == "devicetree":
        import tree_sitter_devicetree as m
    elif name == "python":
        import tree_sitter_python as m
    else:
        raise KeyError(name)
    p = Parser(Language(m.language()))
    _PARSERS[name] = p
    return p


def _walk(node) -> Iterable:
    """Pre-order traversal without recursion limits."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _text(n) -> str:
    return n.text.decode("utf8", "replace")


def _first_ident(node, types=("identifier", "type_identifier", "field_identifier")):
    for x in _walk(node):
        if x.type in types:
            return _text(x)
    return None


# ---- C -------------------------------------------------------------------- #

C_TARGETS = {
    "function_definition": "function",
    "declaration": "variable",
    "type_definition": "type",
    "struct_specifier": "type",
    "union_specifier": "type",
    "enum_specifier": "type",
    "preproc_def": "macro",
    "preproc_function_def": "macro",
}
C_CONTAINERS = {"translation_unit", "preproc_if", "preproc_ifdef", "preproc_else",
                "preproc_elif", "preproc_elifdef", "linkage_specification",
                # tree-sitter error recovery wraps whole stretches of a file in ERROR when it
                # meets an attribute macro or a macro-generated definition it cannot parse;
                # the definitions inside are still top-level for our purposes
                "ERROR"}


def _error_descend(node):
    """A tag comment whose next sibling is an ERROR node (recovery wrapper)
    binds to the first real node inside it."""
    n = node
    for _ in range(4):
        if n is None or n.type != "ERROR":
            return n
        n = next((c for c in n.named_children if c.type != "comment"), None)
    return n


def c_symbol(node) -> str | None:
    n = node
    for _ in range(8):                      # follow declarator chain
        d = n.child_by_field_name("declarator")
        if d is None:
            break
        n = d
    if n.type in ("identifier", "type_identifier", "field_identifier"):
        return _text(n)
    for fld in ("name", "declarator"):
        c = node.child_by_field_name(fld)
        if c is not None and c.type in ("identifier", "type_identifier"):
            return _text(c)
    # struct/enum specifier used directly in a declaration: `struct foo {..} bar;`
    if node.type == "declaration":
        t = node.child_by_field_name("type")
        if t is not None and t.type in ("struct_specifier", "enum_specifier", "union_specifier"):
            nm = t.child_by_field_name("name")
            if nm is not None:
                return _text(nm)
    return _first_ident(n) or _first_ident(node)


def _c_toplevel(node) -> bool:
    p = node.parent
    while p is not None:
        if p.type not in C_CONTAINERS:
            return False
        p = p.parent
    return True


def scan_c(src: bytes):
    tree = _parser("c").parse(src)
    comments, targets, by_id = [], [], {}
    for n in _walk(tree.root_node):
        if n.type == "comment":
            comments.append((n, Comment(_text(n), n.start_byte, n.end_byte,
                                        n.start_point[0] + 1, n.end_point[0] + 1)))
        elif n.type in C_TARGETS:
            # skip a `declaration` that is really the body of a struct field etc.
            t = Target(C_TARGETS[n.type], c_symbol(n), None, n.start_byte, n.end_byte,
                       n.start_point[0] + 1, n.end_point[0] + 1, _c_toplevel(n))
            t.qualified = t.symbol
            targets.append(t)
            by_id[n.id] = t
    _bind_next_sibling(comments, by_id, comment_type="comment", descend=_error_descend)
    # tree-sitter's recovery sometimes swallows a whole function into an ERROR node
    # (attribute macros, #if-alternated signatures, statement expressions). A tag
    # comment left unbound is then matched textually against the next line.
    for node, rec in comments:
        if rec.target is None and "@wiki:" in rec.text:
            t = _c_regex_fallback(src, node.end_byte, rec.line_end)
            if t is not None:
                targets.append(t)
                rec.target = t
    return [c for _, c in comments], targets


_C_SIG_RE = re.compile(rb"^[ \t]*(?:[A-Za-z_]\w*[ \t*]+)+?([A-Za-z_]\w*)[ \t]*\([^;{]*$")


def _c_regex_fallback(src: bytes, from_byte: int, comment_end_line: int):
    """Synthesise a function Target when the line after a tag comment looks like
    a definition signature; the body end is found by brace matching."""
    pos = from_byte
    n = len(src)
    line_no = comment_end_line            # 1-based line of the comment end
    # skip blank lines and preprocessor lines (an #elif between signature variants)
    while pos < n:
        eol = src.find(b"\n", pos)
        eol = n if eol < 0 else eol
        line = src[pos:eol]
        stripped = line.strip()
        if stripped and not stripped.startswith(b"#") and not stripped.startswith(b"//"):
            break
        pos = eol + 1
        line_no += 1
        if line_no - comment_end_line > 3:
            return None
    else:
        return None
    m = _C_SIG_RE.match(src[pos:eol])
    if not m or src[pos:eol].strip().startswith((b"return", b"if", b"else", b"while", b"for")):
        return None
    name = m.group(1).decode()
    brace = src.find(b"{", eol)
    if brace < 0:
        return None
    depth, i = 0, brace
    while i < n:
        c = src[i:i + 1]
        if c == b"{":
            depth += 1
        elif c == b"}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    end = i + 1 if i < n else n
    start_line = line_no                  # line_no now names the signature line
    end_line = start_line + src[pos:end].count(b"\n")
    return Target("function", name, name, pos, end, start_line, end_line, toplevel=True)


# ---- YAML ----------------------------------------------------------------- #

def _yaml_key(pair) -> str | None:
    k = pair.child_by_field_name("key")
    return _text(k).strip() if k is not None else None


def _yaml_descend(node):
    """From a comment's next sibling, dive to the first concrete pair/item."""
    n = node
    for _ in range(12):
        if n is None:
            return None
        if n.type in ("block_mapping_pair", "flow_pair", "block_sequence_item", "flow_node"):
            return n
        if n.type in ("document", "block_node", "block_mapping", "block_sequence",
                      "flow_mapping", "flow_sequence", "stream"):
            nxt = next((c for c in n.named_children if c.type != "comment"), None)
            n = nxt
            continue
        return n
    return n


def _yaml_path(node) -> str:
    parts = []
    p = node
    while p is not None:
        if p.type in ("block_mapping_pair", "flow_pair"):
            parts.append(_yaml_key(p) or "?")
        elif p.type == "block_sequence_item" and p.parent is not None:
            idx = [c for c in p.parent.named_children if c.type == "block_sequence_item"].index(p)
            parts.append(f"[{idx}]")
        p = p.parent
    return ".".join(reversed(parts))


def scan_yaml(src: bytes):
    tree = _parser("yaml").parse(src)
    comments, targets, by_id = [], [], {}
    for n in _walk(tree.root_node):
        if n.type == "comment":
            comments.append((n, Comment(_text(n), n.start_byte, n.end_byte,
                                        n.start_point[0] + 1, n.end_point[0] + 1)))
        elif n.type in ("block_mapping_pair", "flow_pair"):
            key = _yaml_key(n)
            t = Target("key", key, _yaml_path(n), n.start_byte, n.end_byte,
                       n.start_point[0] + 1, n.end_point[0] + 1, toplevel=True)
            targets.append(t); by_id[n.id] = t
        elif n.type == "block_sequence_item":
            q = _yaml_path(n)
            t = Target("item", q.rsplit(".", 1)[-1], q, n.start_byte, n.end_byte,
                       n.start_point[0] + 1, n.end_point[0] + 1, toplevel=False)
            targets.append(t); by_id[n.id] = t
    _bind_next_sibling(comments, by_id, comment_type="comment", descend=_yaml_descend, climb=True)
    return [c for _, c in comments], targets


# ---- Devicetree ----------------------------------------------------------- #

def _dts_node_name(n) -> str | None:
    name = n.child_by_field_name("name")
    if name is None:
        return None
    if name.type == "reference":                    # &label { ... }
        return _text(name).strip()
    label = n.child_by_field_name("label")
    s = _text(name).strip()
    addr = n.child_by_field_name("address")
    # the grammar attaches '@' and the unit_address both as `address`; take the last
    addrs = [c for i, c in enumerate(n.children) if n.field_name_for_child(i) == "address"
             and c.type == "unit_address"]
    if addrs:
        s = f"{s}@{_text(addrs[-1]).strip()}"
    if label is not None and label.type == "identifier":
        return f"{_text(label).strip()}: {s}"
    return s


def _dts_symbol(n) -> str | None:
    """Bare symbol a human would type in `refs:`: the label if there is one,
    else the node name (with @addr), else &reference, else property name."""
    if n.type == "node":
        label = n.child_by_field_name("label")
        if label is not None and label.type == "identifier":
            return _text(label).strip()
        full = _dts_node_name(n)
        return full
    if n.type == "property":
        nm = n.child_by_field_name("name")
        return _text(nm).strip() if nm is not None else None
    if n.type in ("preproc_def", "preproc_function_def"):
        nm = n.child_by_field_name("name")
        return _text(nm).strip() if nm is not None else None
    return None


def _dts_path(n) -> str:
    parts = []
    p = n
    while p is not None:
        if p.type == "node":
            parts.append(_dts_node_name(p) or "?")
        elif p.type == "property":
            parts.append(_dts_symbol(p) or "?")
        p = p.parent
    return "/".join(reversed(parts)).replace("/: ", "/")


def scan_devicetree(src: bytes):
    tree = _parser("devicetree").parse(src)
    comments, targets, by_id = [], [], {}
    for n in _walk(tree.root_node):
        if n.type == "comment":
            comments.append((n, Comment(_text(n), n.start_byte, n.end_byte,
                                        n.start_point[0] + 1, n.end_point[0] + 1)))
        elif n.type in ("node", "property", "preproc_def", "preproc_function_def"):
            kind = {"node": "node", "property": "property"}.get(n.type, "macro")
            t = Target(kind, _dts_symbol(n), _dts_path(n) if n.type != "preproc_def" else _dts_symbol(n),
                       n.start_byte, n.end_byte, n.start_point[0] + 1, n.end_point[0] + 1,
                       toplevel=True)
            targets.append(t); by_id[n.id] = t
    _bind_next_sibling(comments, by_id, comment_type="comment", descend=_error_descend)
    return [c for _, c in comments], targets


# ---- shared binding rule for tree-sitter languages ------------------------ #

def _bind_next_sibling(comments, by_id, comment_type, descend, climb=False, max_gap=2):
    """A tag comment binds to the next named sibling that is not itself a
    comment, optionally descending (YAML) into the first concrete child.
    Contiguous comments before a target may all carry tags; each binds to
    that same target. With `climb`, a comment that ends a nested block (YAML
    attaches a comment between two top-level keys to the *previous* mapping)
    looks at the enclosing nodes' next siblings instead. The target must start
    within `max_gap` lines of the last comment, so a stray comment never binds
    to something far below it."""
    for node, rec in comments:
        cur, sib = node, node.next_named_sibling
        while sib is None and climb and cur.parent is not None:
            cur = cur.parent
            sib = cur.next_named_sibling
        last_line = node.end_point[0]
        while sib is not None and sib.type == comment_type:
            last_line = sib.end_point[0]
            sib = sib.next_named_sibling
        if sib is None:
            continue
        if descend is not None:
            sib = descend(sib)
            if sib is None:
                continue
        if sib.start_point[0] - last_line > max_gap:
            continue
        rec.target = by_id.get(sib.id)


# --------------------------------------------------------------------------- #
# line family
# --------------------------------------------------------------------------- #

@dataclass
class LineRules:
    comment: str = "#"
    symbol_res: list = field(default_factory=list)       # regexes with group 1 = symbol
    block_indent: bool = False                           # indented lines continue the statement
    kind: str = "statement"
    statement_res: list = field(default_factory=list)    # comment-looking lines that are really statements


_LINE_RULES = {
    "conf": LineRules(symbol_res=[re.compile(r"^\s*(CONFIG_\w+)\s*="),
                                  re.compile(r"^\s*#\s*(CONFIG_\w+)\s+is not set")],
                      statement_res=[re.compile(r"^\s*#\s*CONFIG_\w+\s+is not set")]),
    "make": LineRules(symbol_res=[re.compile(r"^\s*(?:export\s+)?([A-Za-z_][\w\-.]*)\s*[:+?!]?="),
                                  re.compile(r"^([\w\-./%$()]+)\s*:"),
                                  re.compile(r"^\s*(?:ifeq|ifneq|ifdef|ifndef)\s*\(?\s*\$?\(?([\w\-.]+)")],
                      block_indent=True),
    "kconfig": LineRules(symbol_res=[re.compile(r"^\s*(?:menu)?config\s+(\w+)"),
                                     re.compile(r"^\s*(?:choice|menu|source|rsource|osource)\s+\"?([^\"\n]+)")],
                         block_indent=True),
    "cmake": LineRules(symbol_res=[re.compile(r"^\s*(?:set|function|macro|option|add_library|add_executable|"
                                              r"zephyr_library_named|target_sources)\s*\(\s*([\w\-.${}]+)", re.I),
                                   re.compile(r"^\s*([A-Za-z_]\w*)\s*\(")]),
    "shell": LineRules(symbol_res=[re.compile(r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)"),
                                   re.compile(r"^\s*(?:export\s+|declare\s+-\w+\s+)?([A-Za-z_]\w*)="),
                                   re.compile(r"^\s*(?:function\s+)([A-Za-z_]\w*)")],
                       block_indent=True),
}


def _make_line_scanner(rules: LineRules):
    cchar = rules.comment

    def scan(src: bytes):
        text = src.decode("utf8", "replace")
        lines = text.split("\n")
        # byte offsets of each line start
        offs, pos = [], 0
        for ln in lines:
            offs.append(pos)
            pos += len(ln.encode("utf8")) + 1
        comments, targets = [], []
        i, n = 0, len(lines)
        pending: list[Comment] = []
        while i < n:
            raw = lines[i]
            s = raw.strip()
            if not s:
                i += 1
                continue
            is_stmt = any(rx.match(raw) for rx in rules.statement_res)
            if s.startswith(cchar) and not is_stmt:
                # a run of comment lines is one comment record
                j = i
                while (j + 1 < n and lines[j + 1].strip().startswith(cchar)
                       and not any(rx.match(lines[j + 1]) for rx in rules.statement_res)):
                    j += 1
                block = "\n".join(lines[i:j + 1])
                c = Comment(block, offs[i], offs[j] + len(lines[j].encode("utf8")), i + 1, j + 1)
                comments.append(c)
                pending.append(c)
                i = j + 1
                continue
            # statement: this line + continuations (+ indented block)
            j = i
            while j < n and lines[j].rstrip().endswith("\\") and j + 1 < n:
                j += 1
            if rules.block_indent:
                k = j + 1
                while k < n:
                    nxt = lines[k]
                    if not nxt.strip():
                        # blank lines inside an indented block are fine only if more block follows
                        look = k + 1
                        while look < n and not lines[look].strip():
                            look += 1
                        if look < n and (lines[look].startswith((" ", "\t"))) and not lines[look].strip().startswith(cchar):
                            k = look
                            continue
                        break
                    if nxt.startswith((" ", "\t")) or nxt.strip() in ("}", "fi", "done", "esac", "endif"):
                        j = k
                        k += 1
                        continue
                    break
            sym = None
            for rx in rules.symbol_res:
                m = rx.match(raw)
                if m:
                    sym = m.group(1).strip()
                    break
            t = Target(rules.kind, sym, sym, offs[i], offs[j] + len(lines[j].encode("utf8")),
                       i + 1, j + 1, toplevel=not raw.startswith((" ", "\t")))
            targets.append(t)
            for c in pending:
                # only comments immediately above (no blank line in between) bind
                if c.line_end == i or all(not lines[x].strip() for x in range(c.line_end, i)):
                    c.target = t
            pending = []
            i = j + 1
        return comments, targets
    return scan


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

def _python_name(node):
    if node.type == "decorated_definition":
        node = node.child_by_field_name("definition")
    if node.type in ("function_definition", "class_definition"):
        name = node.child_by_field_name("name")
        return _text(name) if name else None
    if node.type == "assignment":
        name = node.child_by_field_name("left")
        return _text(name) if name and name.type == "identifier" else None
    return None


# @wiki:impl languages.python
def scan_python(src: bytes):
    root = _parser("python").parse(src).root_node
    targets, comments = [], []
    for node in _walk(root):
        if node.type == "comment":
            sibling = node.next_named_sibling
            last = node
            while sibling is not None and sibling.type == "comment":
                last, sibling = sibling, sibling.next_named_sibling
            # Tree-sitter places the leading comment of a Python suite outside
            # its block, so descend to the block's first statement.
            if sibling is not None and sibling.type == "block":
                sibling = next((child for child in sibling.named_children if child.type != "comment"), None)
            target = None
            if sibling is not None and sibling.start_point[0] - last.end_point[0] <= 2:
                target = _python_target(sibling)
            comments.append(Comment(_text(node), node.start_byte, node.end_byte,
                                    node.start_point[0] + 1, node.end_point[0] + 1, target))
        if node.parent is not None and node.parent.type == "decorated_definition":
            continue
        target = _python_target(node)
        if target:
            targets.append(target)
    return comments, targets


def _python_target(node):
    original = node
    if node.type == "expression_statement" and node.named_child_count == 1:
        node = node.named_children[0]
    if node.type == "assignment" and original.type != "expression_statement":
        return None
    name = _python_name(node)
    if not name:
        return None
    ancestors = []
    parent = original.parent
    while parent:
        if parent.type in ("function_definition", "class_definition"):
            ancestors.append(_python_name(parent))
        parent = parent.parent
    actual = node.child_by_field_name("definition") if node.type == "decorated_definition" else node
    kind = {"function_definition": "function", "class_definition": "type"}.get(actual.type, "variable")
    return Target(kind, name, ".".join([*reversed(ancestors), name]), original.start_byte,
                  original.end_byte, original.start_point[0] + 1, original.end_point[0] + 1,
                  toplevel=True)


LANGUAGES: dict[str, LangSpec] = {
    "python": LangSpec("python", "python", scan_python, "#"),
    "c": LangSpec("c", "c", scan_c, "/*"),
    "yaml": LangSpec("yaml", "yaml", scan_yaml, "#"),
    "devicetree": LangSpec("devicetree", "dts", scan_devicetree, "/*"),
    "conf": LangSpec("conf", "kconfig", _make_line_scanner(_LINE_RULES["conf"]), "#"),
    "make": LangSpec("make", "makefile", _make_line_scanner(_LINE_RULES["make"]), "#"),
    "kconfig": LangSpec("kconfig", "kconfig", _make_line_scanner(_LINE_RULES["kconfig"]), "#"),
    "cmake": LangSpec("cmake", "cmake", _make_line_scanner(_LINE_RULES["cmake"]), "#"),
    "shell": LangSpec("shell", "bash", _make_line_scanner(_LINE_RULES["shell"]), "#"),
}

# extension / basename -> language, used when the config does not override
DEFAULT_FILE_MAP = {
    ".py": "python",
    ".c": "c", ".h": "c",
    ".yaml": "yaml", ".yml": "yaml",
    ".dts": "devicetree", ".dtsi": "devicetree", ".overlay": "devicetree",
    ".conf": "conf", ".defconfig": "conf",
    ".mk": "make", "Makefile": "make", "makefile": "make", "GNUmakefile": "make",
    "Kconfig": "kconfig",
    ".cmake": "cmake", "CMakeLists.txt": "cmake",
    ".sh": "shell", ".bash": "shell",
}


def language_for(path, file_map: dict[str, str]) -> LangSpec | None:
    """Match by basename first (Kconfig, CMakeLists.txt), then by suffix."""
    name = getattr(path, "name", str(path))
    key = file_map.get(name)
    if key is None:
        suf = getattr(path, "suffix", "")
        key = file_map.get(suf)
    if key is None:
        return None
    return LANGUAGES.get(key)


TAG_RE = re.compile(r"@wiki:(\w+)\s+([A-Za-z0-9_.\-/]+)")


def parse_tag_comment(text: str, strip_chars: str = "/*#"):
    """Return ([(role, anchor)], note) from a comment's raw text."""
    tags, note_lines = [], []
    for raw in text.splitlines():
        line = raw.strip()
        # peel comment decoration from both ends
        line = line.lstrip("/*#!").strip()
        if line.endswith("*/"):
            line = line[:-2].strip()
        line = line.lstrip("*").strip()
        m = TAG_RE.search(line)
        if m:
            tags.append((m.group(1), m.group(2)))
        elif line:
            note_lines.append(line)
    return tags, " ".join(note_lines).strip()
