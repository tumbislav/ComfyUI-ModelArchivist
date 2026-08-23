# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_workflow_scanner.py
# purpose: Tests for workflow file validation and reconciliation
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

import backend.files.scanner as scanner_module
from backend.files.scanner import Scanner, read_workflow_candidate
from backend.repository.tables import Workflow, WorkflowError


def write_workflow(path: Path, workflow_id: str, config=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'id': workflow_id}
    if config is not None:
        data['config'] = config
    path.write_text(json.dumps(data), encoding='utf-8')


def scan_workflows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, list, Scanner]:
    working = tmp_path / 'working'
    archive = tmp_path / 'archive'
    working.mkdir(exist_ok=True)
    archive.mkdir(exist_ok=True)
    saved = []
    monkeypatch.setattr(scanner_module.repo, 'save_scanned_workflow',
                        lambda workflow, _tags: saved.append(workflow))
    scanner = Scanner(start_time=scanner_module.datetime.datetime.now(
        tz=scanner_module.datetime.timezone.utc))
    scanner.barrier = SimpleNamespace(wait=lambda: None)
    return working, archive, saved, scanner


def test_unreadable_json_and_non_uuid_files_are_ignored(tmp_path: Path):
    invalid_json = tmp_path / 'invalid.json'
    invalid_json.write_text('{', encoding='utf-8')
    invalid_uuid = tmp_path / 'invalid_uuid.json'
    invalid_uuid.write_text(json.dumps({'id': 'not-a-uuid'}), encoding='utf-8')

    assert read_workflow_candidate(invalid_json, tmp_path, 'w') is None
    assert read_workflow_candidate(invalid_uuid, tmp_path, 'w') is None


def test_invalid_config_marks_workflow_as_erroneous(tmp_path: Path):
    workflow_file = tmp_path / 'workflow.json'
    write_workflow(workflow_file, str(uuid4()), {'name': 42, 'tags': 'not-a-list'})

    candidate = read_workflow_candidate(workflow_file, tmp_path, 'w')

    assert candidate is not None
    assert candidate.errors == {WorkflowError.INVALID_CONFIG}


@pytest.mark.parametrize(
    ('where', 'expected_error'),
    [
        ('working', WorkflowError.DUPLICATE_WORKING),
        ('archive', WorkflowError.DUPLICATE_ARCHIVE),
    ],
)
def test_duplicate_ids_in_one_location_are_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    where: str,
    expected_error: WorkflowError,
):
    working, archive, saved, scanner = scan_workflows(tmp_path, monkeypatch)
    root = working if where == 'working' else archive
    workflow_id = str(uuid4())
    write_workflow(root / 'one.json', workflow_id)
    write_workflow(root / 'nested' / 'two.json', workflow_id)

    scanner.find_workflows([(working, archive)])

    assert len(saved) == 1
    assert expected_error.value in saved[0].errors
    assert saved[0].read_only is True


def test_working_archive_location_mismatch_is_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    working, archive, saved, scanner = scan_workflows(tmp_path, monkeypatch)
    workflow_id = str(uuid4())
    write_workflow(working / 'one.json', workflow_id)
    write_workflow(archive / 'nested' / 'two.json', workflow_id)

    scanner.find_workflows([(working, archive)])

    assert len(saved) == 1
    assert saved[0].errors == [WorkflowError.LOCATION_MISMATCH.value]
    assert saved[0].read_only is True
    locations = {
        (component_set.where, component_set.primary_dir,
         component.relative_path, component.file_name)
        for component_set in saved[0].component_sets
        for component in component_set.components
    }
    assert locations == {
        ('w', working.as_posix(), '', 'one.json'),
        ('a', archive.as_posix(), 'nested', 'two.json'),
    }


def test_workflow_errors_are_persisted(tmp_path: Path):
    engine = create_engine(f'sqlite:///{tmp_path / "workflow.db"}')
    SQLModel.metadata.create_all(engine)
    workflow_id = str(uuid4())
    workflow = Workflow(id=workflow_id,
                        file_name='workflow',
                        internal_name='Workflow',
                        purpose='',
                        relative_path='',
                        deployment='working',
                        touched='timestamp',
                        errors=[WorkflowError.INVALID_CONFIG.value])

    with Session(engine) as session:
        session.add(workflow)
        session.commit()
        session.expire_all()
        stored = session.get(Workflow, workflow_id)

        assert stored is not None
        assert stored.errors == [WorkflowError.INVALID_CONFIG.value]
        assert stored.read_only is True
    engine.dispose()
