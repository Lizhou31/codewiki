from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from codewiki.build import run
from codewiki.config import Wiki
from codewiki.documents import read_document
from codewiki.init_project import main as init
from codewiki.languages import scan_python, parse_tag_comment
from codewiki.query import query, main as query_cli
from codewiki.snapshot import freshness


@pytest.fixture
def instance(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'main.py').write_text('# @wiki:impl architecture.dispatch\ndef dispatch(value):\n    return value + 1\n')
    assert init(['--root', str(tmp_path), '--code-root', 'src', '--name', 'Name "quoted": value']) == 0
    w = Wiki(tmp_path / 'codewiki/wiki.config.yaml')
    (w.wiki_dir / 'architecture.md').write_text('''---
id: architecture
title: Architecture
summary: Dispatches work.
---

## TL;DR

- A compact entry point.

## Concepts

### Dispatch {#dispatch}

Keep **original emphasis** and [links](https://example.com).

#### Details {#details}

```python
## Not a heading
```

### Other {#other}

Another section.
''')
    return w


def build(w):
    rc, warnings, ix = run(w, strict=True, quiet=True)
    assert rc == 0, [(x.kind, x.message) for x in warnings]
    return ix


def test_progressive_queries_preserve_markdown_and_source(instance):
    ix = build(instance)
    overview = query(instance, ix, 'doc', 'architecture')
    assert 'markdown' not in overview
    selected = query(instance, ix, 'section', 'architecture.dispatch', limit=200)
    assert '**original emphasis**' in selected['markdown']
    assert '#### Details' in selected['markdown']
    assert '### Other' not in selected['markdown']
    assert not any(s['title'] == 'Not a heading' for s in ix['docs'][0]['sections'])
    first = query(instance, ix, 'source', 'src.main.dispatch', limit=1)
    second = query(instance, ix, 'source', 'src.main.dispatch', offset=first['next_offset'], limit=1)
    assert first['markdown'] == 'def dispatch(value):\n'
    assert second['markdown'] == '    return value + 1\n'
    assert second['next_offset'] is None


def test_freshness_rejects_old_source_ranges_and_detects_additions(instance):
    ix = build(instance)
    src = instance.abs('../src/main.py')
    src.write_text('\n\n' + src.read_text())
    assert freshness(instance, ix)['state'] == 'stale'
    with pytest.raises(ValueError, match='stale'):
        query(instance, ix, 'source', 'dispatch')
    ix = build(instance)
    (src.parent / 'added.py').write_text('def new(): pass\n')
    assert '../src/added.py' in freshness(instance, ix)['changed']
    (src.parent / 'added.py').unlink()
    src.unlink()
    assert '../src/main.py' in freshness(instance, ix)['changed']


def test_duplicate_heading_fails_without_replacing_valid_outputs(instance):
    build(instance)
    before = instance.index_path.read_bytes()
    html = (instance.site_dir / 'architecture.html').read_bytes()
    page = instance.wiki_dir / 'architecture.md'
    page.write_text(page.read_text() + '\n### Duplicate {#dispatch}\n')
    rc, warnings, _ = run(instance, strict=True, quiet=True)
    assert rc == 1
    assert any('duplicate' in x.message for x in warnings)
    assert instance.index_path.read_bytes() == before
    assert (instance.site_dir / 'architecture.html').read_bytes() == html


@pytest.mark.parametrize('extra', [
    'parent: missing\n', 'related: [missing]\n',
    'decisions: [{id: rationale, reason: evidence, anchors: [missing.anchor]}]\n',
])
def test_broken_relationships_fail(instance, extra):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', 'title: Architecture\n' + extra))
    rc, warnings, _ = run(instance, strict=True, quiet=True)
    assert rc == 1
    assert any(x.kind.startswith('broken-') for x in warnings)


def test_hierarchy_cycle_and_duplicate_document(instance):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture', 'parent: child\ntitle: Architecture'))
    child = instance.wiki_dir / 'child.md'
    child.write_text('---\nid: child\nparent: architecture\n---\n## Child\n')
    assert any(x.kind == 'hierarchy-cycle' for x in run(instance, strict=True, quiet=True)[1])
    child.write_text('---\nid: architecture\n---\n## Child\n')
    assert any(x.kind == 'duplicate-doc' for x in run(instance, strict=True, quiet=True)[1])


def test_hierarchy_navigation_and_partial_theme(instance):
    (instance.wiki_dir / 'child.md').write_text('---\nid: child\nparent: architecture\nsummary: Child summary\n---\n## Child\n')
    theme = instance.wiki_dir / '_theme'
    theme.mkdir()
    (theme / 'style.css').write_text('/* project override */')
    ix = build(instance)
    tree = query(instance, ix, 'tree', limit=1)
    assert tree['items'][0]['id'] == 'architecture'
    assert tree['next_offset'] == 1
    assert query(instance, ix, 'tree', offset=1)['items'][0]['depth'] == 1
    html = (instance.site_dir / 'architecture.html').read_text()
    assert 'child.html' in html and 'Child summary' in html
    assert (instance.site_dir / 'style.css').read_text() == '/* project override */'
    assert (instance.site_dir / 'vendor/mermaid.min.js').is_file()
    assert (instance.site_dir / 'vendor/LICENSE.mermaid').is_file()


def test_init_preserves_customization_and_uses_package_assets(instance):
    root = instance.root.parent
    page = instance.wiki_dir / 'architecture.md'
    before = page.read_bytes()
    assert init(['--root', str(root), '--name', 'New name']) == 0
    assert page.read_bytes() == before
    assert instance.cfg['project']['name'] == 'Name "quoted": value'
    assert not (instance.wiki_dir / '_theme').exists()
    assert not (instance.root / 'codewiki').exists()
    assert (instance.root / 'skills/wiki-query/SKILL.md').is_file()
    with pytest.raises(ValueError):
        init(['--root', str(root), '--dir', '../outside'])


def test_cli_json_and_config_on_either_side(instance, capsys):
    build(instance)
    capsys.readouterr()
    assert query_cli(['--config', str(instance.cfg_path), '--json', 'tree']) == 0
    assert json.loads(capsys.readouterr().out)['items'][0]['id'] == 'architecture'
    assert query_cli(['doc', 'architecture', '--config', str(instance.cfg_path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['document']['id'] == 'architecture'
    assert query_cli(['source', 'does-not-exist', '--json', '--config', str(instance.cfg_path)]) == 2
    assert 'error' in json.loads(capsys.readouterr().out)


def test_file_lookup_does_not_silently_choose_duplicate_basename(instance):
    other = instance.abs('../src/nested/main.py')
    other.parent.mkdir()
    other.write_text('def other(): pass\n')
    ix = build(instance)
    with pytest.raises(ValueError, match='ambiguous'):
        query(instance, ix, 'file', 'main.py')
    assert query(instance, ix, 'file', '../src/main.py')['covered'] is True


def test_python_decorators_scopes_and_comments():
    src = b'''class Worker:
    # @wiki:impl work.dispatch
    @staticmethod
    def dispatch(value):
        return value

# @wiki:impl work.entry
# Supporting note.
async def entry():
    pass
'''
    comments, targets = scan_python(src)
    bound = {aid: comment.target for comment in comments for _, aid in parse_tag_comment(comment.text)[0]}
    target = bound['work.dispatch']
    assert target.qualified == 'Worker.dispatch'
    assert src[target.start_byte:target.end_byte].startswith(b'@staticmethod')
    assert bound['work.entry'].symbol == 'entry'
    assert len([t for t in targets if t.qualified == 'Worker.dispatch']) == 1


@pytest.mark.parametrize('text', [
    'No frontmatter', '---\nid: x\n', '---\nid: ../../escape\n---\n',
    '---\nid: index\n---\n', '---\nid: x\nrefs: invalid\n---\n',
    '---\nid: x\nrelated: wrong\n---\n',
])
def test_invalid_markdown_is_a_validation_error(tmp_path, text):
    page = tmp_path / 'bad.md'
    page.write_text(text)
    with pytest.raises(ValueError):
        read_document(page)


def test_theme_failure_preserves_index_and_site(instance):
    build(instance)
    before = instance.index_path.read_bytes()
    html = (instance.site_dir / 'architecture.html').read_bytes()
    theme = instance.wiki_dir / '_theme'
    theme.mkdir()
    (theme / 'page.html.j2').write_text('{% invalid syntax %}')
    with pytest.raises(ValueError, match='theme rendering failed'):
        run(instance, strict=True, quiet=True)
    assert instance.index_path.read_bytes() == before
    assert (instance.site_dir / 'architecture.html').read_bytes() == html


def test_removed_document_retires_generated_page(instance):
    child = instance.wiki_dir / 'child.md'
    child.write_text('---\nid: child\nparent: architecture\n---\n## Child\n')
    build(instance)
    assert (instance.site_dir / 'child.html').is_file()
    child.unlink()
    build(instance)
    assert not (instance.site_dir / 'child.html').exists()


def test_old_index_requests_rebuild_instead_of_empty_results(instance, capsys):
    instance.index_path.write_text('{"docs": [], "by_file": {}}')
    capsys.readouterr()
    assert query_cli(['tree', '--json', '--config', str(instance.cfg_path)]) == 2
    assert 'run codewiki build' in json.loads(capsys.readouterr().out)['error']


@pytest.mark.parametrize('extra', [
    'depends_on: [missing]\n',
    'diagram_links: {engine: missing}\n',
    'diagram_links: {engine: architecture.missing}\n',
])
def test_broken_architecture_links_preserve_published_outputs(instance, extra):
    build(instance)
    before = instance.index_path.read_bytes()
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', 'title: Architecture\n' + extra))
    rc, warnings, _ = run(instance, strict=True, quiet=True)
    assert rc == 1
    assert any(x.kind in ('broken-dependency', 'broken-diagram-link') for x in warnings)
    assert instance.index_path.read_bytes() == before


@pytest.mark.parametrize('extra', [
    'depends_on: wrong\n', 'depends_on: [3]\n',
    'diagram_links: []\n', 'diagram_links: {node: 3}\n',
    'diagram_links: {node: "javascript:alert(1)"}\n',
])
def test_invalid_architecture_metadata(instance, extra):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', 'title: Architecture\n' + extra))
    with pytest.raises(ValueError):
        read_document(path)


def test_diagrams_share_dependencies_with_cli_and_resolve_exact_ids(instance):
    from codewiki.build import parse_doc, diagram_targets
    from codewiki.query import render_text
    child = instance.wiki_dir / 'child.md'
    child.write_text('''---
id: engine.v2
title: Engine
parent: architecture
depends_on: [architecture]
---
## Internals {#run}
Implementation explanation.
''')
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', '''title: Architecture
diagram_links:
  engine: engine.v2
  details: engine.v2.run
''') + '\n## Map\n\n```mermaid\nflowchart LR\n engine --> details\n```\n')
    ix = build(instance)
    result = query(instance, ix, 'doc', 'architecture')
    assert result['document']['used_by'] == ['engine.v2']
    assert result['document']['diagram_links']['details'] == 'engine.v2.run'
    assert 'Used by: engine.v2' in render_text(result)
    assert query(instance, ix, 'doc', 'engine.v2')['document']['depends_on'] == ['architecture']
    docs = [parse_doc(instance, p, []) for p in (path, child)]
    targets = diagram_targets(docs[0], docs)
    assert targets['engine']['href'] == 'engine.v2.html'
    assert targets['details']['href'] == 'engine.v2.html#run'  # Explicit mapping overrides local slug.
    assert targets['dispatch']['href'] == '#dispatch'  # Legacy local nodes still work.
    assert targets['engine.v2']['href'] == 'engine.v2.html'  # Automatic document node.
    html = (instance.site_dir / 'architecture.html').read_text()
    assert 'href="engine.v2.html#run"' in html  # Non-JS destination link.
    assert 'id="diagram-targets"' in html
    assert (instance.site_dir / 'diagrams.js').is_file()


def test_dependency_cycles_do_not_become_parent_cycles(instance):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', 'title: Architecture\ndepends_on: [child]\n'))
    (instance.wiki_dir / 'child.md').write_text('---\nid: child\nparent: architecture\ndepends_on: [architecture]\n---\n## Child\n')
    ix = build(instance)
    assert ix['docs'][0]['used_by'] == ['child']
