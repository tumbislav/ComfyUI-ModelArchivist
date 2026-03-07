# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from ..db.tables import Model, Tag, Component, Workflow

import uuid
import logging
from enum import StrEnum
from typing import List
from threading import Thread, Lock, Barrier
from pathlib import Path
from ..config import config
from ..db.repository import repo
from ..model.file_handler import scan_models, scan_workflows

logger = logging.getLogger('model_archivist')


class ScanStatus(StrEnum):
    INACTIVE = 'inactive'
    RUNNING = 'scanning'
    CLEANUP = 'completed'
    ERROR = 'error'


class Scanner:

    def __init__(self):
        self.id: str | None = None

        self.status: ScanStatus = ScanStatus.INACTIVE
        self.models_scanned: int | None = None
        self.workflows_scanned: int | None = None
        self.hashes_calculated: int | None = None
        self.errors: List[str] = []

        self.status_lock = Lock()
        self.repo_lock = Lock()

    def start(self, models: dict, workflows: dict, rehash: bool = False) -> str | None:
        with self.status_lock:
            status = self.status

        if status != ScanStatus.INACTIVE:
            return None

        with self.status_lock:
            self.status = ScanStatus.RUNNING
            self.id = str(uuid.uuid1())

        model_args = [(name, active, archive, rehash)
                      for name, locations in models.items()
                      for active, archive in locations]
        total_threads = len(model_args) + (1 if workflows is None else 2)
        barrier = Barrier(total_threads)

        for arg in model_args:
            Thread(target=self.scan_models, args=(barrier, *arg)).start()
        if workflows is not None:
            Thread(target=self.scan_workflows, args=(barrier, workflows[0], workflows[1])).start()
        Thread(target=self.cleanup, args=(barrier,)).start()
        for name, active, archive, rehash in model_args:
            self.scan_models(barrier, name, active, archive, rehash)
        self.cleanup(barrier)

        return self.id

    def scan_models(self, barrier: Barrier, type_name: str, active: Path, archive: Path, rehash: bool):
        logger.info(f'Scanner.scan_models: {self.id} starting scan for {type_name} in {active} and {archive}')
        for model_dict in scan_models(active, archive, config.model_extensions, rehash):
            archive_count = sum(1 if is_archive else 0 for fn, ft, is_archive in model_dict['files'])
            logger.info(f'Scanner: located model {model_dict["name"]}')
            model = Model(hash=model_dict['hash'],
                          name=model_dict['name'],
                          relative_path=model_dict['relative_path'],
                          type=type_name,
                          active_type_dir=str(active),
                          archive_type_dir=str(archive),
                          is_archived=archive_count > 0,
                          is_active=archive_count < len(model_dict['files']),
                          last_scan_id=self.id,
                          components=[Component(file_name=str(file_path.name),
                                                file_dir=str(file_path.parent),
                                                component_type=file_type,
                                                is_archive=is_archive,
                                                last_scan_id=self.id)
                                      for file_path, file_type, is_archive in model_dict['files']],
                          scan_errors='')
            with self.repo_lock:
                repo.save_model(model, model_dict['tags'])
        logger.info(f'Scanner.scan_models: {self.id} ending scan for {type_name} in {active} and {archive}')
        barrier.wait()

    def scan_workflows(self, barrier: Barrier, active: Path, archive: Path):
        logger.info(f'{self.id} starting workflow scan')
        for workflow_dict in scan_workflows(active, archive):
            pass

        logger.info(f'{self.id} ending workflow scan')
        barrier.wait()

    def cleanup(self, barrier: Barrier):
        barrier.wait()
        with self.status_lock:
            self.status = ScanStatus.CLEANUP
        logger.info(f'{self.id} starting cleanup')
        with self.repo_lock:
            repo.clean_repository(self.id)
        with self.status_lock:
            self.status = ScanStatus.INACTIVE
        logger.info(f'{self.id} done')


scanner = Scanner()
