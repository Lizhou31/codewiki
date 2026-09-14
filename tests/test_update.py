from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from codewiki import instance_files, update
from codewiki.__main__ import main as cli
from codewiki.config import Wiki
from codewiki.init_project import main as init


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    resources = tmp_path / 'resources'
    shutil.copytree(instance_files.RESOURCES, resources)
    monkeypatch.setattr(instance_files, 'RESOURCES', resources)
    assert init(['--root', str(root), '--dir', 'docs/team wiki']) == 0
    return root, Wiki(root / 'docs/team wiki/wiki.config.yaml'), resources


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


# @wiki:impl updates.tests
def test_refresh_upgrades_known_files_preserves_project_content_and_is_repeatable(project, monkeypatch):
    root, wiki, resources = project
    preserved = ['wiki/architecture.md', 'wiki.config.yaml', 'reviews/notes.json',
                 'wiki/_theme/style.css', 'site/index.html', 'index.json']
    for name in preserved[2:]:
        path = wiki.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('project-owned content')
    before = {name: (wiki.root / name).read_bytes() for name in preserved}
    root_before = (root / 'AGENTS.md').read_bytes()
    (resources / 'skills/wiki-query/SKILL.md').write_text('New query instructions\n')
    (resources / 'templates/decision.md').write_text('New decision template\n')
    (resources / 'integrations/new-example.sh').write_text('new example\n')
    monkeypatch.setattr(instance_files, '__version__', '9.0.0')
    assert cli(['update', '--installed', '--config', str(wiki.cfg_path)]) == 0
    assert (wiki.root / 'skills/wiki-query/SKILL.md').read_text() == 'New query instructions\n'
    assert (wiki.wiki_dir / '_templates/decision.md').read_text() == 'New decision template\n'
    assert (wiki.root / 'integrations/new-example.sh').is_file()
    assert all((wiki.root / name).read_bytes() == data for name, data in before.items())
    assert (root / 'AGENTS.md').read_bytes() == root_before
    assert instance_files.read_manifest(wiki.root)['framework_version'] == '9.0.0'
    after = snapshot(root)
    assert cli(['update', '--installed', '--config', str(wiki.cfg_path)]) == 0
    assert snapshot(root) == after


# @wiki:impl updates.tests
def test_customizations_conflict_only_when_package_changes_and_can_be_adopted(project):
    root, wiki, resources = project
    local = wiki.root / 'skills/wiki-query/SKILL.md'
    local.write_text('My customized instructions\n')
    args = ['update', '--installed', '--config', str(wiki.cfg_path)]
    assert cli(args) == 0
    assert local.read_text() == 'My customized instructions\n'
    baseline = instance_files.read_manifest(wiki.root)['files'][local.relative_to(wiki.root).as_posix()]
    # Rerunning init must not bless custom text as the original package copy.
    init(['--root', str(root), '--dir', 'docs/team wiki'])
    assert instance_files.read_manifest(wiki.root)['files'][local.relative_to(wiki.root).as_posix()] == baseline
    (resources / 'skills/wiki-query/SKILL.md').write_text('New upstream instructions\n')
    before = snapshot(root)
    assert cli(args + ['--dry-run']) == 1
    assert snapshot(root) == before
    assert cli(args) == 1
    assert local.read_text() == 'My customized instructions\n'
    incoming = wiki.root / instance_files.INCOMING / 'skills/wiki-query/SKILL.md'
    assert incoming.read_text() == 'New upstream instructions\n'
    local.write_bytes(incoming.read_bytes())
    assert cli(args) == 0


# @wiki:impl updates.tests
def test_legacy_adopts_matching_files_but_preserves_unknown_content(project):
    root, wiki, resources = project
    (wiki.root / instance_files.MANIFEST).unlink()
    (wiki.root / 'AGENTS.md').write_text('Old or customized instance guide\n')
    args = ['update', '--installed', '--config', str(wiki.cfg_path), '--root', str(root)]
    assert cli(args) == 1
    manifest = instance_files.read_manifest(wiki.root)
    assert 'AGENTS.md' not in manifest['files']
    assert 'skills/wiki-query/SKILL.md' in manifest['files']
    assert manifest['framework_version'] is None
    assert (wiki.root / 'AGENTS.md').read_text() == 'Old or customized instance guide\n'


# @wiki:impl updates.tests
def test_acknowledging_a_merge_preserves_it_until_the_next_package_change(project):
    root, wiki, resources = project
    name = 'skills/wiki-query/SKILL.md'
    local = wiki.root / name
    upstream = resources / 'skills/wiki-query/SKILL.md'
    local.write_text('My merged instructions\n')
    upstream.write_text('New package instructions\n')
    args = ['update', '--installed', '--config', str(wiki.cfg_path)]
    assert cli(args) == 1
    before = snapshot(root)
    assert cli(args + ['--keep-local', 'wiki/architecture.md']) == 2
    assert snapshot(root) == before
    assert cli(args + ['--keep-local', name, '--dry-run']) == 0
    assert snapshot(root) == before
    assert cli(args + ['--keep-local', name]) == 0
    assert local.read_text() == 'My merged instructions\n'
    assert cli(args) == 0
    upstream.write_text('Another package revision\n')
    assert cli(args) == 1


# @wiki:impl updates.tests
def test_custom_wiki_directory_is_used(project, capsys):
    root, wiki, resources = project
    new_dir = wiki.root / 'manual'
    wiki.wiki_dir.rename(new_dir)
    wiki.cfg_path.write_text(wiki.cfg_path.read_text().replace('wiki_dir: wiki', 'wiki_dir: manual'))
    (root / 'AGENTS.md').unlink()
    before = snapshot(root)
    assert cli(['update', '--installed', '--dry-run', '--config', str(wiki.cfg_path)]) == 0
    assert snapshot(root) == before
    assert 'would add root guidance' in capsys.readouterr().out
    assert cli(['update', '--installed', '--config', str(wiki.cfg_path)]) == 0
    assert not (wiki.root / 'wiki').exists()
    assert 'docs/team wiki/manual/_templates/' in (wiki.root / 'AGENTS.md').read_text()
    assert '`docs/team wiki/AGENTS.md`' in (root / 'AGENTS.md').read_text()


# @wiki:impl updates.tests
@pytest.mark.parametrize('obstacle', ['symlink', 'parent-file', 'manifest'])
def test_invalid_paths_fail_before_writes(project, obstacle):
    root, wiki, resources = project
    if obstacle == 'manifest':
        (wiki.root / instance_files.MANIFEST).write_text('{"schema_version": 99}')
    else:
        target = wiki.root / instance_files.INCOMING
        if obstacle == 'symlink':
            target.symlink_to(resources, target_is_directory=True)
        else:
            target.write_text('not a directory')
    before = snapshot(root)
    outside_before = snapshot(resources)
    assert cli(['update', '--installed', '--config', str(wiki.cfg_path)]) == 2
    assert snapshot(root) == before
    assert snapshot(resources) == outside_before


# @wiki:impl updates.tests
def test_installer_selection_pins_current_python_and_source(project, monkeypatch):
    root, wiki, resources = project
    monkeypatch.setattr(update.importlib.util, 'find_spec', lambda name: object())
    assert update.installer_command()[:3] == [sys.executable, '-m', 'pip']
    assert update.installer_command()[-1] == 'codewiki-framework'
    source = root / 'framework source'
    source.mkdir()
    (source / 'pyproject.toml').write_text('[project]\nname="codewiki-framework"\n')
    assert update.installer_command(source)[-1] == f'codewiki-framework @ {source.as_uri()}'
    monkeypatch.setattr(update.importlib.util, 'find_spec', lambda name: None)
    monkeypatch.setattr(update.shutil, 'which', lambda name: '/tool/uv')
    command = update.installer_command()
    assert command[command.index('--python') + 1] == sys.executable
    monkeypatch.setattr(update.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='No installer'):
        update.installer_command()


# @wiki:impl updates.tests
@pytest.mark.parametrize('installer_result,refresh_result', [(3, 0), (0, 1), (0, 0)])
def test_install_then_reenter_new_release_and_propagate_failures(project, monkeypatch, installer_result, refresh_result):
    root, wiki, resources = project
    monkeypatch.setattr(update, 'installer_command', lambda source: ['installer', 'codewiki-framework'])
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert Path(kwargs['cwd']) != root
        return subprocess.CompletedProcess(command, installer_result if len(calls) == 1 else refresh_result)
    monkeypatch.setattr(update.subprocess, 'run', run)
    before = snapshot(root)
    args = ['update', '--config', str(wiki.cfg_path)]
    assert cli(args + ['--dry-run']) == 0
    assert not calls
    assert cli(args) == (installer_result or refresh_result)
    assert snapshot(root) == before
    if installer_result:
        assert len(calls) == 1
    else:
        assert calls[1] == [sys.executable, '-m', 'codewiki', 'update', '--installed',
                            '--config', str(wiki.cfg_path), '--root', str(root)]
