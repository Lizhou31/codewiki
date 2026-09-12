"""Binding tests for every language in the registry.

    python -m tests.test_languages        # from the plugin root
    pytest tests/                          # if you have pytest
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from codewiki.languages import LANGUAGES, parse_tag_comment  # noqa: E402


# @wiki:impl test-languages.binding
def bound(lang: str, src: str):
    comments, targets = LANGUAGES[lang].scan(src.encode())
    out = {}
    for c in comments:
        tags, note = parse_tag_comment(c.text, LANGUAGES[lang].comment_strip)
        for _, anchor in tags:
            out[anchor] = (c.target.symbol if c.target else None,
                           c.target.kind if c.target else "file", note)
    return out, targets


# @wiki:impl test-languages.parsers
def test_c():
    src = """
/* file header */
#include <x.h>
/* @wiki:impl k.macro */
#define FOO(x) ((x) + 1)
// @wiki:gotcha k.type
typedef struct { int a; } my_t;
/* @wiki:impl k.enum */
enum colour { RED, GREEN };
/* @wiki:impl k.var
 * a global with a note */
static uint8_t table[4] = {0};
/* @wiki:entry k.fn
 * Called from the tick. */
static void oem_key_scan(uint8_t raw)
{
    int local = 0;
}
#if defined(FEATURE)
/* @wiki:impl k.cond */
void guarded(void) {}
#endif
/* @wiki:impl k.proto */
int prototype(int a);
"""
    b, targets = bound("c", src)
    assert b["k.macro"][:2] == ("FOO", "macro"), b
    assert b["k.type"][:2] == ("my_t", "type"), b
    assert b["k.enum"][:2] == ("colour", "type"), b
    assert b["k.var"][:2] == ("table", "variable") and b["k.var"][2] == "a global with a note", b
    assert b["k.fn"] == ("oem_key_scan", "function", "Called from the tick."), b
    assert b["k.cond"][:2] == ("guarded", "function"), b
    assert b["k.proto"][:2] == ("prototype", "variable"), b
    top = {t.symbol for t in targets if t.toplevel}
    assert {"FOO", "my_t", "colour", "table", "oem_key_scan", "guarded", "prototype"} <= top, top
    assert "local" not in top


# @wiki:impl test-languages.parsers
def test_yaml():
    src = """# header
# @wiki:impl b.versions
versions:
  # @wiki:impl b.sdk
  sdk: 1.2
  zephyr: 3.7
# @wiki:impl b.p721
p721:
  board: evk
  list:
    # @wiki:impl b.item
    - a
    - b
"""
    b, targets = bound("yaml", src)
    assert b["b.versions"][:2] == ("versions", "key"), b
    assert b["b.sdk"][:2] == ("sdk", "key"), b
    assert b["b.p721"][:2] == ("p721", "key"), b
    assert b["b.item"][1] == "item", b
    q = {t.qualified for t in targets}
    assert {"versions", "versions.sdk", "versions.zephyr", "p721.board", "p721.list"} <= q, q


# @wiki:impl test-languages.parsers
def test_devicetree():
    src = """#include <dt.h>
/ {
    // @wiki:impl h.fstab
    fstab { compatible = "x"; };
};
/* @wiki:gotcha h.spim
 * bus note */
&spim0 {
    frequency = <8000000>;
    /* @wiki:impl h.sensor */
    motion_sensor: aimpointpro2@0 {
        // @wiki:impl h.cpi
        cpi = <1600>;
        irq-gpios = <&gpio0 5 GPIO_ACTIVE_LOW>;
    };
};
/* @wiki:impl h.def */
#define FOO 1
"""
    b, targets = bound("devicetree", src)
    assert b["h.fstab"][:2] == ("fstab", "node"), b
    assert b["h.spim"] == ("&spim0", "node", "bus note"), b
    assert b["h.sensor"][:2] == ("motion_sensor", "node"), b
    assert b["h.cpi"][:2] == ("cpi", "property"), b
    assert b["h.def"][:2] == ("FOO", "macro"), b
    q = {t.qualified for t in targets}
    assert "&spim0/motion_sensor: aimpointpro2@0/cpi" in q, q
    syms = {t.symbol for t in targets}
    assert {"motion_sensor", "&spim0", "cpi", "irq-gpios", "frequency"} <= syms, syms


# @wiki:impl test-languages.statements
def test_conf():
    src = """# comment

# @wiki:impl c.nkey
CONFIG_AIR_KEY_REMAP_SUPPORT_NKEY=y
CONFIG_OTHER=n

# @wiki:gotcha c.stack
# needed by profile switch
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=4096
# @wiki:impl c.unset
# CONFIG_FOO is not set
"""
    b, _ = bound("conf", src)
    assert b["c.nkey"][:2] == ("CONFIG_AIR_KEY_REMAP_SUPPORT_NKEY", "statement"), b
    assert b["c.stack"] == ("CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE", "statement", "needed by profile switch"), b
    assert b["c.unset"][0] == "CONFIG_FOO", b


# @wiki:impl test-languages.statements
def test_make():
    src = """# @wiki:impl m.flag
AIR_KEY_DEB_LEADING_EDGE = y
# @wiki:impl m.rule
all: dep \\
     other
\t$(CC) -o x
# @wiki:impl m.ifeq
ifeq ($(AIR_FOO),y)
CFLAGS += -DAIR_FOO
endif
"""
    b, targets = bound("make", src)
    assert b["m.flag"][0] == "AIR_KEY_DEB_LEADING_EDGE", b
    assert b["m.rule"][0] == "all", b
    assert b["m.ifeq"][0] == "AIR_FOO", b
    rule = next(t for t in targets if t.symbol == "all")
    assert rule.line_end == 6, rule   # continuation + recipe line included


# @wiki:impl test-languages.statements
def test_kconfig():
    src = """# @wiki:impl k.opt
config OEM_SLIDE_SWITCH_WARM_RESET
\tbool "warm reset on slide"
\tdepends on AIR_TRIPLE_MODE_SLIDE_SWITCH
\thelp
\t  reboots instead of handing over

config OTHER
\tbool
"""
    b, targets = bound("kconfig", src)
    assert b["k.opt"][0] == "OEM_SLIDE_SWITCH_WARM_RESET", b
    t = next(t for t in targets if t.symbol == "OEM_SLIDE_SWITCH_WARM_RESET")
    assert t.line_end == 6, t


# @wiki:impl test-languages.statements
def test_cmake():
    src = """# @wiki:impl cm.def
zephyr_compile_definitions(AIR_HID_DEVICE_SCENARIO_SERVICE_KEY_REMAP)
# @wiki:impl cm.set
set(RISCV_FEATURES a;b)
"""
    b, _ = bound("cmake", src)
    assert b["cm.def"][0] == "zephyr_compile_definitions", b
    assert b["cm.set"][0] == "RISCV_FEATURES", b


# @wiki:impl test-languages.statements
def test_shell():
    src = """#!/bin/bash
# @wiki:impl sh.fn
load_build_config() {
    local x=1
}
# @wiki:impl sh.var
IMAGE_TAG="${ZEPHYR_VERSION}-branch"
"""
    b, targets = bound("shell", src)
    assert b["sh.fn"][0] == "load_build_config", b
    assert b["sh.var"][0] == "IMAGE_TAG", b
    fn = next(t for t in targets if t.symbol == "load_build_config")
    assert fn.line_end == 5, fn


# @wiki:impl test-languages.binding
def test_parse_tag_comment_styles():
    for text in ("/* @wiki:impl a.b\n * note here */", "// @wiki:impl a.b\n// note here",
                 "# @wiki:impl a.b\n# note here", "#! @wiki:impl a.b"):
        tags, note = parse_tag_comment(text)
        assert tags == [("impl", "a.b")], text
        assert note in ("note here", ""), (text, note)


if __name__ == "__main__":
    import inspect
    ok = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            fn(); ok += 1
            print(f"  ok  {name}")
    print(f"{ok} tests passed")
