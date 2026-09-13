"""Observable review lifecycle and CI contracts."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from codewiki.build import run, Warning
from codewiki.config import Wiki
from codewiki.init_project import main as init
from codewiki.review import acknowledge, report, main as review_cli
from codewiki.snapshot import freshness
from codewiki.serve import watch_paths, fingerprint


@pytest.fixture
def wiki(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/main.py').write_text('# @wiki:impl engine.run\ndef run():\n    return 1\n')
    root = tmp_path / 'codewiki'
    (root / 'wiki').mkdir(parents=True)
    (root / 'wiki.config.yaml').write_text('code_roots: [../src]\n')
    (root / 'wiki/engine.md').write_text('---\nid: engine\ntitle: Engine\n---\n## Run {#run}\nReturns a value.\n')
    return Wiki(root / 'wiki.config.yaml')


def item(w):
    return report(w)['documents'][0]


def approve(w, outcome='no-change', reason='Checked return behavior; description remains correct.'):
    value = item(w)
    return acknowledge(w, value['document'], outcome=outcome, reason=reason, expected=value['fingerprint'])


# @wiki:impl reviews.tests
def test_live_lifecycle_and_rebuild_never_acknowledges(wiki):
    assert not wiki.index_path.exists()
    assert item(wiki)['state'] == 'unreviewed'
    page = wiki.wiki_dir / 'engine.md'
    original = page.read_bytes()
    approve(wiki)
    assert report(wiki)['ok']
    assert page.read_bytes() == original
    source = wiki.abs('../src/main.py')
    source.write_text(source.read_text().replace('return 1', 'return 2'))
    assert item(wiki)['state'] == 'outdated'
    previous = (wiki.root / 'reviews/engine.json').read_bytes()
    rc, warnings, ix = run(wiki, strict=True, quiet=True)
    assert rc == 0
    assert any(w.kind == 'outdated-doc' for w in warnings)
    assert ix['reviews']['pending'] == 1
    assert 'Documentation review: outdated' in (wiki.site_dir / 'engine.html').read_text()
    assert (wiki.root / 'reviews/engine.json').read_bytes() == previous
    assert item(wiki)['state'] == 'outdated'
    approve(wiki)
    assert report(wiki)['ok']
    assert freshness(wiki, ix)['state'] == 'stale'
    assert run(wiki, strict=True, quiet=True)[2]['reviews']['pending'] == 0


# @wiki:impl reviews.tests
def test_uncovered_source_is_not_a_documentation_requirement(wiki):
    approve(wiki)
    extra = wiki.abs('../src/uncovered.py')
    extra.write_text('def independent(): return 1\n')
    assert report(wiki)['ok']
    extra.write_text('def independent(): return 2\n')
    assert report(wiki)['ok']
    extra.unlink()
    assert report(wiki)['ok']


# @wiki:impl reviews.tests
def test_updated_requires_prose_change_and_reason(wiki):
    approve(wiki)
    with pytest.raises(ValueError, match='unchanged'):
        approve(wiki, outcome='updated')
    with pytest.raises(ValueError, match='nonempty'):
        approve(wiki, reason='  ')
    page = wiki.wiki_dir / 'engine.md'
    page.write_text(page.read_text() + '\nReview explains the returned value.\n')
    assert item(wiki)['state'] == 'outdated'
    saved = approve(wiki, outcome='updated', reason='Clarified the returned value.')
    assert saved['outcome'] == 'updated'
    assert report(wiki)['ok']


# @wiki:impl reviews.tests
def test_expected_rejects_changes_after_inspection(wiki):
    value = item(wiki)
    source = wiki.abs('../src/main.py')
    source.write_text(source.read_text() + '\n# additional change\n')
    with pytest.raises(ValueError, match='inputs changed'):
        acknowledge(wiki, 'engine', outcome='no-change', reason='Reviewed', expected=value['fingerprint'])
    assert not (wiki.root / 'reviews/engine.json').exists()


# @wiki:impl reviews.tests
def test_removed_tag_remains_visible_until_reviewed(wiki):
    approve(wiki)
    source = wiki.abs('../src/main.py')
    source.write_text('def run(): return 1\n')
    status = item(wiki)
    assert status['state'] == 'outdated'
    change = next(c for c in status['changes'] if c['kind'] == 'source')
    assert change['path'] == '../src/main.py'
    assert change['previous'] and change['current'] is None
    assert status['previous']['snapshot']['coverage'][0]['anchor'] == 'engine.run'
    approve(wiki, reason='Page now describes the general concept; source binding intentionally removed.')
    assert report(wiki)['ok']


# @wiki:impl reviews.tests
def test_moved_tag_tracks_old_and_new_file(wiki):
    approve(wiki)
    wiki.abs('../src/main.py').rename(wiki.abs('../src/moved.py'))
    state = item(wiki)
    assert state['state'] == 'outdated'
    assert {c['path'] for c in state['changes'] if c['kind'] == 'source'} == {'../src/main.py', '../src/moved.py'}
    approve(wiki)
    assert report(wiki)['ok']


# @wiki:impl reviews.tests
@pytest.mark.parametrize('binding', ['owns', 'refs'])
def test_document_side_coverage_tracks_content(wiki, binding):
    page = wiki.wiki_dir / 'engine.md'
    if binding == 'owns':
        path = wiki.abs('../src/style.css')
        path.write_text('body { color: black; }')
        metadata = 'owns: [../src/style.css]\n'
    else:
        path = wiki.abs('../src/vendor.py')
        path.write_text('def external(): return 1\n')
        metadata = 'refs: [{file: ../src/vendor.py, symbols: [external]}]\n'
    page.write_text(page.read_text().replace('title: Engine\n', 'title: Engine\n' + metadata))
    approve(wiki)
    ix = run(wiki, strict=True, quiet=True)[2]
    before = fingerprint(wiki, watch_paths(wiki))
    path.write_text(path.read_text() + '\n')
    assert freshness(wiki, ix)["state"] == "stale"
    assert fingerprint(wiki, watch_paths(wiki)) != before
    assert item(wiki)['state'] == 'outdated'
    assert any(c.get('path') == wiki.rel(path) for c in item(wiki)['changes'])


# @wiki:impl reviews.tests
def test_missing_owned_source_is_not_waived(wiki):
    page = wiki.wiki_dir / 'engine.md'
    page.write_text(page.read_text().replace('title: Engine\n', 'title: Engine\nowns: [../src/main.py]\n'))
    approve(wiki)
    wiki.abs('../src/main.py').unlink()
    assert report(wiki)['errors']
    with pytest.raises(ValueError, match='structural'):
        approve(wiki)


# @wiki:impl reviews.tests
def test_parser_failure_is_a_ci_error(wiki, monkeypatch):
    import codewiki.build as builder
    scan = builder.scan_code
    def failed(w):
        tags, symbols, diagnostics, count = scan(w)
        return tags, symbols, diagnostics + [Warning('parse-error', 'missing grammar', '../src/main.py')], count
    monkeypatch.setattr(builder, 'scan_code', failed)
    assert review_cli(['check', '--config', str(wiki.cfg_path)]) == 2
    with pytest.raises(ValueError, match='parse errors'):
        approve(wiki)


# @wiki:impl reviews.tests
def test_deleted_document_requires_explicit_retirement(wiki):
    approve(wiki)
    (wiki.wiki_dir / 'engine.md').unlink()
    wiki.abs('../src/main.py').write_text('def run(): return 1\n')
    value = item(wiki)
    assert value['removed'] and value['state'] == 'outdated'
    with pytest.raises(ValueError, match='retire'):
        approve(wiki)
    acknowledge(wiki, 'engine', outcome='retired', reason='Component removed.', expected=value['fingerprint'])
    assert report(wiki)['ok']
    # Reusing a retired ID must not inherit the old approval.
    (wiki.wiki_dir / 'engine.md').write_text('---\nid: engine\n---\n## Replacement\n')
    assert item(wiki)['state'] == 'outdated'


# @wiki:impl reviews.tests
@pytest.mark.parametrize('payload', ['{', '[]', '{"schema_version": 999}'])
def test_bad_records_fail_closed(wiki, payload, capsys):
    folder = wiki.root / 'reviews'
    folder.mkdir()
    (folder / 'engine.json').write_text(payload)
    assert review_cli(['--config', str(wiki.cfg_path), 'check', '--json']) == 2
    response = json.loads(capsys.readouterr().out)
    assert response['ok'] is False and response['error']


# @wiki:impl reviews.tests
def test_cli_exit_codes_and_json(wiki, capsys):
    cfg = str(wiki.cfg_path)
    assert review_cli(['status', '--config', cfg, '--json', '--outdated']) == 0
    assert json.loads(capsys.readouterr().out)['pending'] == 1
    assert review_cli(['--json', '--config', cfg, 'check']) == 1
    assert json.loads(capsys.readouterr().out)['ok'] is False
    approve(wiki)
    assert review_cli(['check', '--config', cfg, '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ok'] is True
    result = subprocess.run([sys.executable, '-m', 'codewiki', 'review', 'check', '--config', cfg, '--json'], capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['ok']


# @wiki:impl reviews.tests
def test_review_files_are_watched_and_scaffold_is_portable(wiki):
    before = fingerprint(wiki, watch_paths(wiki))
    approve(wiki)
    assert fingerprint(wiki, watch_paths(wiki)) != before
    assert init(['--root', str(wiki.root.parent)]) == 0
    assert (wiki.root / 'skills/wiki-review/SKILL.md').is_file()
    assert (wiki.root / 'integrations/check-docs.sh').is_file()
    assert (wiki.root / 'integrations/github-actions.yml').is_file()
    # Reinitializing must preserve both custom integrations and review records.
    integration = wiki.root / 'integrations/pre-push'
    integration.write_text('custom hook')
    record = (wiki.root / 'reviews/engine.json').read_bytes()
    init(['--root', str(wiki.root.parent)])
    assert integration.read_text() == 'custom hook'
    assert (wiki.root / 'reviews/engine.json').read_bytes() == record


# @wiki:impl reviews.tests
def test_deleting_record_reopens_baseline(wiki):
    approve(wiki)
    (wiki.root / 'reviews/engine.json').unlink()
    assert item(wiki)['state'] == 'unreviewed'
    assert not report(wiki)['ok']


# @wiki:impl reviews.tests
def test_content_changes_do_not_depend_on_timestamps(wiki):
    import os
    approve(wiki)
    path = wiki.abs('../src/main.py')
    stat = path.stat()
    path.write_text(path.read_text().replace('return 1', 'return 2'))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert item(wiki)['state'] == 'outdated'


# @wiki:impl reviews.tests
def test_only_affected_existing_document_is_outdated(wiki):
    (wiki.wiki_dir / 'manual.md').write_text('---\nid: manual\n---\n## Setup\nRead the guide.\n')
    approve(wiki)
    state = report(wiki)
    manual = next(d for d in state['documents'] if d['document'] == 'manual')
    acknowledge(wiki, 'manual', outcome='no-change', reason='Checked standalone procedure.', expected=manual['fingerprint'])
    wiki.abs('../src/main.py').write_text('# @wiki:impl engine.run\ndef run(): return 3\n')
    state = report(wiki)
    assert state['pending'] == 1
    assert {d['document']: d['state'] for d in state['documents']} == {'engine': 'outdated', 'manual': 'current'}
    page = wiki.wiki_dir / 'manual.md'
    page.write_text(page.read_text() + '\nAdditional instruction.\n')
    assert report(wiki)['pending'] == 2


# @wiki:impl reviews.tests
def test_missing_config_is_machine_readable_error(tmp_path, capsys):
    assert review_cli(['check', '--config', str(tmp_path / 'absent.yaml'), '--json']) == 2
    assert json.loads(capsys.readouterr().out)['ok'] is False


# @wiki:impl reviews.tests
def test_unreviewed_site_and_compact_query_status(wiki):
    from codewiki.query import query
    rc, diagnostics, ix = run(wiki, strict=True, quiet=True)
    assert rc == 0
    assert any(d.kind == 'unreviewed-doc' for d in diagnostics)
    overview = (wiki.site_dir / 'index.html').read_text()
    assert 'Documentation review' in overview and 'unreviewed' in overview
    summary = query(wiki, ix, 'doc', 'engine')['document']['review']
    assert summary == {'state': 'unreviewed', 'reason': 'No review baseline'}
    assert not list((wiki.root / 'reviews').glob('*.json'))


# @wiki:impl reviews.tests
def test_invalid_record_preserves_published_outputs(wiki):
    approve(wiki)
    run(wiki, strict=True, quiet=True)
    original = wiki.index_path.read_bytes()
    page = (wiki.site_dir / 'engine.html').read_bytes()
    (wiki.root / 'reviews/engine.json').write_text('{}')
    with pytest.raises(ValueError, match='unsupported'):
        run(wiki, strict=True, quiet=True)
    assert wiki.index_path.read_bytes() == original
    assert (wiki.site_dir / 'engine.html').read_bytes() == page
