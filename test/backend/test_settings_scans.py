# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_settings_scans.py
# purpose: Per-type save isolation, batch scan requests, and configuration locks
# ---------------------------------------------------------------------------

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import backend.dispatcher as dispatch
from backend.server.routers import admin, configuration, user_types


@pytest.fixture
def unlocked(monkeypatch):
    worker = dispatch.OperationDispatcher()
    monkeypatch.setattr(dispatch, '_get_scanner', lambda: None)
    monkeypatch.setattr(configuration, 'dispatcher', worker)
    monkeypatch.setattr(user_types, 'dispatcher', worker)
    return worker


def test_single_model_save_preserves_other_types(unlocked, monkeypatch):
    original = {'model_types': [
        {'name': 'first', 'display_name': 'First', 'extensions': ['.bin'], 'locations': []},
        {'name': 'second', 'display_name': 'Second', 'extensions': ['.pt'], 'locations': []},
    ]}
    monkeypatch.setattr(configuration.repo, 'get_repository_configuration', lambda: deepcopy(original))
    captured = []
    monkeypatch.setattr(configuration.repo, 'update_model_configuration',
                        lambda data: captured.append(data) or data)
    changed = configuration.ModelTypeInput(name='first', display_name='Changed', extensions=['.bin'])

    asyncio.run(configuration.update_single_model_type(changed, 'first'))

    assert captured[0]['model_types'][0]['display_name'] == 'Changed'
    assert captured[0]['model_types'][1] == original['model_types'][1]
    with pytest.raises(HTTPException):
        asyncio.run(configuration.update_single_model_type(changed))
    assert len(captured) == 1


@pytest.mark.parametrize('scope', ['models', 'user_objects'])
def test_batch_scan_is_one_dispatch_with_deduplicated_targets(monkeypatch, scope):
    monkeypatch.setattr(admin, 'get_config', lambda: SimpleNamespace(
        read_only=False, setup_required=False, model_folders={'first': [], 'second': []}))
    monkeypatch.setattr(admin, 'user_types_for_scan', lambda: [{'id': 'first'}, {'id': 'second'}])
    calls = []
    monkeypatch.setattr(admin, 'submit_scan', lambda *args: calls.append(args) or {'id': 'one'})

    result = admin.start_scan(scope=scope, targets=admin.ScanTargets(type_ids=['second', 'first', 'second']))
    assert result['id'] == 'one'
    assert calls == [(False, scope, ['second', 'first'])]
    with pytest.raises(HTTPException):
        admin.start_scan(scope=scope, targets=admin.ScanTargets(type_ids=['first', 'missing']))
    assert len(calls) == 1


def test_empty_batch_cannot_accidentally_become_full_scan():
    with pytest.raises(ValidationError):
        admin.ScanTargets(type_ids=[])


@pytest.mark.parametrize('active_scanner', [False, True])
def test_configuration_writes_blocked_while_operation_active(unlocked, monkeypatch, active_scanner):
    if active_scanner:
        monkeypatch.setattr(dispatch, '_get_scanner', lambda: SimpleNamespace(started=True, finished=False))
    else:
        unlocked._active_id = 'pending-scan'
    model = configuration.ModelTypeInput(name='first', display_name='First', extensions=['.bin'])
    user = user_types.UserTypeInput(name='User', short_name='User', object_class='file',
                                   working_dir='w', archive_dir='a', icon='file')
    for name in ['update_repository_configuration', 'update_model_configuration',
                 'update_workflow_configuration', 'create_user_type', 'update_user_type', 'delete_user_type']:
        monkeypatch.setattr(configuration.repo, name, lambda *args: pytest.fail('must not write'))
    calls = [
        lambda: configuration.update_single_model_type(model, 'first'),
        lambda: configuration.update_model_configuration(configuration.ModelConfigurationInput()),
        lambda: configuration.update_workflow_configuration(configuration.WorkflowConfigurationInput()),
        lambda: configuration.update_repository_configuration(configuration.RepositoryConfigurationInput()),
        lambda: user_types.create_user_type(user),
        lambda: user_types.update_user_type('first', user),
        lambda: user_types.delete_user_type('first', 'confirmation'),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as error:
            asyncio.run(call())
        assert error.value.status_code == 409
        assert error.value.detail['code'] == 'operation_busy'
