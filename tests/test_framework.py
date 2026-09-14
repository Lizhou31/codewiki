from __future__ import annotations

import json
from html.parser import HTMLParser
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


# @wiki:impl test-framework.fixtures
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


# @wiki:impl test-framework.fixtures
def build(w):
    rc, warnings, ix = run(w, strict=True, quiet=True)
    assert rc == 0, [(x.kind, x.message) for x in warnings]
    return ix


# @wiki:impl test-framework.queries
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


# @wiki:impl test-framework.queries
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


# @wiki:impl test-framework.publication
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


# @wiki:impl test-framework.validation
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


# @wiki:impl test-framework.validation
def test_hierarchy_cycle_and_duplicate_document(instance):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture', 'parent: child\ntitle: Architecture'))
    child = instance.wiki_dir / 'child.md'
    child.write_text('---\nid: child\nparent: architecture\n---\n## Child\n')
    assert any(x.kind == 'hierarchy-cycle' for x in run(instance, strict=True, quiet=True)[1])
    child.write_text('---\nid: architecture\n---\n## Child\n')
    assert any(x.kind == 'duplicate-doc' for x in run(instance, strict=True, quiet=True)[1])


# @wiki:impl test-framework.initialization
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


# @wiki:impl test-framework.publication
def test_collapsible_navigation_reveals_current_page_ancestors(instance):
    for page_id, parent in [('child', 'architecture'), ('leaf', 'child'),
                            ('other', None), ('other-leaf', 'other')]:
        (instance.wiki_dir / f'{page_id}.md').write_text(
            f'---\nid: {page_id}\nparent: {parent or "null"}\n---\n## Content\n')
    build(instance)

    class Navigation(HTMLParser):
        def __init__(self, html):
            super().__init__()
            self.stack, self.branches, self.links = [], {}, {}
            self.feed(html.split('<nav class="project-nav"')[1].split('</nav>')[0])

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'details':
                page_id = attrs['data-page-id']
                self.branches[page_id] = ('open' in attrs, tuple(self.stack))
                self.stack.append(page_id)
            elif tag == 'a':
                self.links[attrs['href']] = (tuple(self.stack), attrs.get('aria-current'))

        def handle_endtag(self, tag):
            if tag == 'details':
                self.stack.pop()

    for page in ('index', 'files', 'architecture', 'child', 'leaf'):
        nav = Navigation((instance.site_dir / f'{page}.html').read_text())
        assert nav.branches == {
            'architecture': (page in {'architecture', 'child', 'leaf'}, ()),
            'child': (page in {'child', 'leaf'}, ('architecture',)),
            'other': (False, ()),
        }
        assert nav.links['leaf.html'][0] == ('architecture', 'child')
        assert nav.links['other-leaf.html'][0] == ('other',)
        assert len(nav.links) == 6
        assert next(iter(nav.links)) == 'index.html'
        assert nav.links['index.html'] == ((), 'page' if page == 'index' else None)
        if page not in {'index', 'files'}:
            assert nav.links[f'{page}.html'][1] == 'page'


# @wiki:impl test-framework.publication
def test_manual_is_a_separate_root_with_its_own_reading_path(instance):
    (instance.wiki_dir / 'user-manual.md').write_text(
        '---\nid: user-manual\ntype: manual\nparent: null\n'
        'title: User manual\nsummary: Everyday usage.\n---\n## Start here\n')
    (instance.wiki_dir / 'setup.md').write_text(
        '---\nid: setup\nparent: user-manual\ntitle: Setup\n---\n## Install\n')
    (instance.wiki_dir / 'advanced.md').write_text(
        '---\nid: advanced\nparent: setup\ntitle: Advanced setup\n---\n## Configure\n')
    ix = build(instance)
    tree = query(instance, ix, 'tree')['items']
    assert {item['id'] for item in tree if item['depth'] == 0} == {'architecture', 'user-manual'}
    assert next(item for item in tree if item['id'] == 'setup')['depth'] == 1
    assert next(item for item in tree if item['id'] == 'advanced')['depth'] == 2
    overview = (instance.site_dir / 'index.html').read_text().split('<h2>Start here</h2>')[1]
    assert 'href="user-manual.html"' in overview
    assert 'href="architecture.html"' in overview
    assert overview.index('href="user-manual.html"') < overview.index('href="architecture.html"')
    for page in ('index', 'files', 'user-manual', 'setup', 'advanced', 'architecture'):
        html = (instance.site_dir / f'{page}.html').read_text()
        sidebar = html.split('<nav class="project-nav"')[1].split('</nav>')[0]
        assert sidebar.index('href="index.html"') < sidebar.index('href="user-manual.html"')
        assert sidebar.index('href="user-manual.html"') < sidebar.index('href="architecture.html"')
    for page in ('user-manual', 'setup', 'advanced'):
        html = (instance.site_dir / f'{page}.html').read_text()
        reading_path = html.split('aria-label="Reading path">')[1].split('</div>')[0]
        assert 'href="user-manual.html">User manual</a>' in reading_path
        assert 'Architecture' not in reading_path
        assert 'Implementation' not in reading_path
        if page == 'advanced':
            assert 'href="setup.html">Setup</a>' in reading_path
            assert '<span class="active">Advanced setup</span>' in reading_path
    architecture = (instance.site_dir / 'architecture.html').read_text()
    assert '01 Architecture' in architecture and '03 Implementation' in architecture


# @wiki:impl test-framework.initialization
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


# @wiki:impl test-framework.initialization
@pytest.mark.parametrize('directory', ['codewiki', 'docs/team wiki'])
@pytest.mark.parametrize('existing', [None, b'', b'# Project rules\r\n\r\nKeep existing rules.'])
def test_init_adds_root_guidance_once_and_preserves_existing_rules(tmp_path, directory, existing):
    agents = tmp_path / 'AGENTS.md'
    if existing is not None:
        agents.write_bytes(existing)
    args = ['--root', str(tmp_path), '--dir', directory]
    assert init(args) == 0
    generated = agents.read_bytes()
    assert generated.startswith(existing or b'')
    assert f'`{directory}/AGENTS.md`'.encode() in generated
    assert b"project's source code or documentation" in generated
    guide = tmp_path / directory / 'AGENTS.md'
    assert f'{directory}/wiki.config.yaml' in guide.read_text()
    assert f'{directory}/reviews/*.json' in guide.read_text()

    # Both the root section and the instance guide can be customized safely.
    customized = generated.replace(b'Before working', b'Before working (including tests)')
    agents.write_bytes(customized)
    guide.write_text('Custom instance instructions\n')
    assert init(args) == 0
    assert agents.read_bytes() == customized
    assert guide.read_text() == 'Custom instance instructions\n'


# @wiki:impl test-framework.initialization
def test_init_integrates_older_instances_and_distinguishes_wiki_paths(tmp_path):
    # Simulate an instance created before root-level integration existed.
    guide = tmp_path / 'codewiki/AGENTS.md'
    guide.parent.mkdir()
    guide.write_text('Existing instance guide\n')
    agents = tmp_path / 'AGENTS.md'
    agents.write_text('# Project rules\n')
    assert init(['--root', str(tmp_path)]) == 0
    first = agents.read_bytes()
    assert guide.read_text() == 'Existing instance guide\n'
    assert init(['--root', str(tmp_path), '--dir', 'docs/wiki']) == 0
    both = agents.read_bytes()
    assert both.startswith(first)
    assert b'`docs/wiki/AGENTS.md`' in both
    assert init(['--root', str(tmp_path), '--dir', './docs/wiki/']) == 0
    assert agents.read_bytes() == both


# @wiki:impl test-framework.initialization
@pytest.mark.parametrize('existing', [None, b'# Claude rules\r\n\r\nKeep them.'])
def test_init_client_claude_adds_guide_and_skills(tmp_path, existing):
    claude = tmp_path / 'CLAUDE.md'
    if existing is not None:
        claude.write_bytes(existing)
    # Claude Code integration is opt-in; the generic AGENTS.md reference is always written.
    assert init(['--root', str(tmp_path), '--dir', 'docs/wiki']) == 0
    assert not (tmp_path / '.claude').exists()
    assert (claude.read_bytes() if claude.exists() else None) == existing
    assert init(['--root', str(tmp_path), '--dir', 'docs/wiki', '--client', 'claude', '--client', 'claude']) == 0
    generated = claude.read_bytes()
    assert generated.startswith(existing or b'')
    marker = b'<!-- codewiki:agent-guide docs/wiki/AGENTS.md -->'
    assert generated.count(marker) == 1
    assert b'`docs/wiki/AGENTS.md`' in generated and b'`.claude/skills/`' in generated
    agents = (tmp_path / 'AGENTS.md').read_bytes()
    assert agents.count(marker) == 1 and b'.claude/skills' not in agents
    skills = tmp_path / '.claude/skills'
    assert sorted(p.name for p in skills.iterdir()) == ['wiki-author', 'wiki-build', 'wiki-init', 'wiki-query', 'wiki-review']
    skill = skills / 'wiki-query/SKILL.md'
    assert skill.read_text().startswith('---\nname: wiki-query\n')
    assert skill.read_text() == (tmp_path / 'docs/wiki/skills/wiki-query/SKILL.md').read_text()

    # Customized Claude Code files survive repeated initialization.
    customized = generated.replace(b'Before working', b'Before working (including tests)')
    claude.write_bytes(customized)
    skill.write_text('Custom skill\n')
    assert init(['--root', str(tmp_path), '--dir', 'docs/wiki', '--client', 'claude']) == 0
    assert claude.read_bytes() == customized
    assert skill.read_text() == 'Custom skill\n'
    with pytest.raises(SystemExit):
        init(['--root', str(tmp_path), '--client', 'other'])


# @wiki:impl test-framework.queries
def test_cli_json_and_config_on_either_side(instance, capsys):
    build(instance)
    capsys.readouterr()
    assert query_cli(['--config', str(instance.cfg_path), '--json', 'tree']) == 0
    assert json.loads(capsys.readouterr().out)['items'][0]['id'] == 'architecture'
    assert query_cli(['doc', 'architecture', '--config', str(instance.cfg_path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['document']['id'] == 'architecture'
    assert query_cli(['source', 'does-not-exist', '--json', '--config', str(instance.cfg_path)]) == 2
    assert 'error' in json.loads(capsys.readouterr().out)


# @wiki:impl test-framework.queries
def test_file_lookup_does_not_silently_choose_duplicate_basename(instance):
    other = instance.abs('../src/nested/main.py')
    other.parent.mkdir()
    other.write_text('def other(): pass\n')
    ix = build(instance)
    with pytest.raises(ValueError, match='ambiguous'):
        query(instance, ix, 'file', 'main.py')
    assert query(instance, ix, 'file', '../src/main.py')['covered'] is True


# @wiki:impl test-languages.parsers
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


# @wiki:impl test-framework.validation
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


# @wiki:impl test-framework.publication
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


# @wiki:impl test-framework.publication
def test_removed_document_retires_generated_page(instance):
    child = instance.wiki_dir / 'child.md'
    child.write_text('---\nid: child\nparent: architecture\n---\n## Child\n')
    build(instance)
    assert (instance.site_dir / 'child.html').is_file()
    child.unlink()
    build(instance)
    assert not (instance.site_dir / 'child.html').exists()


# @wiki:impl test-framework.queries
def test_old_index_requests_rebuild_instead_of_empty_results(instance, capsys):
    instance.index_path.write_text('{"docs": [], "by_file": {}}')
    capsys.readouterr()
    assert query_cli(['tree', '--json', '--config', str(instance.cfg_path)]) == 2
    assert 'run codewiki build' in json.loads(capsys.readouterr().out)['error']


# @wiki:impl test-framework.diagrams
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


# @wiki:impl test-framework.diagrams
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


# @wiki:impl test-framework.diagrams
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


# @wiki:impl test-framework.diagrams
def test_dependency_cycles_do_not_become_parent_cycles(instance):
    path = instance.wiki_dir / 'architecture.md'
    path.write_text(path.read_text().replace('title: Architecture\n', 'title: Architecture\ndepends_on: [child]\n'))
    (instance.wiki_dir / 'child.md').write_text('---\nid: child\nparent: architecture\ndepends_on: [architecture]\n---\n## Child\n')
    ix = build(instance)
    assert ix['docs'][0]['used_by'] == ['child']


# @wiki:impl test-framework.translations
def test_html_translations_keep_queries_english_and_links_local(instance):
    (instance.wiki_dir / 'child.md').write_text('---\nid: child\nparent: architecture\ntitle: Child\n---\n## Child\n')
    from codewiki.review import report
    before_review = {d['document']: d['fingerprint'] for d in report(instance)['documents']}
    translation = instance.wiki_dir / 'architecture-ch_tw.md'
    translation.write_text('''---
id: architecture
title: 架構
summary: 工作分派。
---
## 重點 {#tl-dr}
- 精簡的入口。
## 概念 {#concepts}
### 分派 {#dispatch}
保留 **原始強調**。[下一頁](child.html#child) [Markdown](child.md#child)
[網站](https://example.com/child.html) [總覽](index.html)
```html
<a href="child.html">literal</a>
```
#### 細節 {#details}
程式碼。
### 其他 {#other}
另一個章節。
''')
    ix = build(instance)
    assert {d['document']: d['fingerprint'] for d in report(instance)['documents']} == before_review
    assert [d['id'] for d in ix['docs']] == ['architecture', 'child']
    assert ix['docs'][0]['title'] == 'Architecture'
    assert '**original emphasis**' in query(instance, ix, 'section', 'architecture.dispatch')['markdown']
    assert '原始強調' not in json.dumps(ix['docs'], ensure_ascii=False)
    html = (instance.site_dir / 'architecture-ch_tw.html').read_text()
    assert '<html lang="zh-TW">' in html
    assert '<h1>架構</h1>' in html
    assert 'href="architecture.html" lang="en"' in html
    assert 'href="child-ch_tw.html#child"' in html
    assert 'href="https://example.com/child.html"' in html
    assert '&lt;a href=&quot;child.html&quot;&gt;' in html
    assert 'def dispatch(value)' in html
    assert 'id="dispatch"' in html
    fallback = (instance.site_dir / 'child-ch_tw.html').read_text()
    assert '此頁尚未翻譯' in fallback and '<div lang="en">' in fallback
    overview = (instance.site_dir / 'index-ch_tw.html').read_text()
    assert 'href="architecture-ch_tw.html"' in overview and '架構' in overview
    files = (instance.site_dir / 'files-ch_tw.html').read_text()
    assert 'href="architecture-ch_tw.html#dispatch"' in files
    translation.unlink()
    build(instance)
    assert not (instance.site_dir / 'architecture-ch_tw.html').exists()
    assert not (instance.site_dir / 'index-ch_tw.html').exists()
    assert (instance.site_dir / 'architecture.html').exists()


# @wiki:impl test-framework.translations
@pytest.mark.parametrize('filename,content', [
    ('missing-ch_tw.md', '---\nid: missing\n---\n'),
    ('architecture-ch_tw.md', '---\nid: other\n---\n'),
    ('architecture-ch_tw.md', '---\nid: architecture\n---\n## Missing anchors\n'),
    ('architecture-ch_tw.md', 'not frontmatter'),
])
def test_invalid_translation_preserves_published_outputs(instance, filename, content):
    build(instance)
    before = instance.index_path.read_bytes()
    before_html = (instance.site_dir / 'architecture.html').read_bytes()
    (instance.wiki_dir / filename).write_text(content)
    rc, warnings, _ = run(instance, strict=True, quiet=True)
    assert rc == 1
    assert any(w.kind in ('invalid-doc', 'invalid-translation') for w in warnings)
    assert instance.index_path.read_bytes() == before
    assert (instance.site_dir / 'architecture.html').read_bytes() == before_html


# @wiki:impl test-framework.translations
def test_translation_aliases_nested_paths_and_diagrams(instance):
    folder = instance.wiki_dir / 'nested'
    folder.mkdir()
    (folder / 'engine.md').write_text('''---
id: engine.v2
title: Engine
parent: architecture
diagram_links:
  dispatch: architecture.dispatch
---
## Engine {#engine}
```mermaid
flowchart LR
  dispatch --> engine
```
''')
    (folder / 'engine-zh_tw.md').write_text('''---
id: engine.v2
title: 引擎
---
## 引擎 {#engine}
[架構](../architecture.md#dispatch)
```mermaid
flowchart LR
  dispatch --> engine
```
''')
    build(instance)
    html = (instance.site_dir / 'engine.v2-ch_tw.html').read_text()
    assert 'href="architecture-ch_tw.html#dispatch"' in html
    assert '"href": "architecture-ch_tw.html#dispatch"' in html
    assert '<h1>引擎</h1>' in html
    (folder / 'engine-ch_tw.md').write_text((folder / 'engine-zh_tw.md').read_text())
    assert run(instance, strict=True, quiet=True)[0] == 1


# @wiki:impl test-framework.translations
def test_multiple_html_locales_and_output_collision(instance):
    original = (instance.wiki_dir / 'architecture.md').read_text()
    for locale in ('ch_tw', 'fr_fr'):
        (instance.wiki_dir / f'architecture-{locale}.md').write_text(original)
    build(instance)
    french = (instance.site_dir / 'architecture-fr_fr.html').read_text()
    assert '<html lang="fr-FR">' in french
    assert 'href="architecture-ch_tw.html"' in french
    assert 'href="architecture.html" lang="en"' in french
    (instance.wiki_dir / 'architecture-ch_tw.md').unlink()
    build(instance)
    assert not (instance.site_dir / 'architecture-ch_tw.html').exists()
    assert (instance.site_dir / 'architecture-fr_fr.html').is_file()
    # A canonical ID must never overwrite a translated page, even in non-strict builds.
    before = instance.index_path.read_bytes()
    (instance.wiki_dir / 'collision.md').write_text('---\nid: architecture-fr_fr\n---\n')
    with pytest.raises(ValueError, match='collides'):
        run(instance, quiet=True)
    assert instance.index_path.read_bytes() == before
