# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: File system scan
# ---------------------------------------------------------------------------

import os
import threading
import logging
from typing import Iterable, Set
from pathlib import Path

logger = logging.getLogger('model_archivist')


def iter_model_files(root_dirs: Iterable[Path], extensions: Set[str]) -> Iterable[Path]:
    for root in root_dirs:
        if not root.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            dpath = Path(dirpath)
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in extensions:
                    yield dpath / fname


class Scanner(threading.Thread):
    """
    Full library scan
    """
    def __init__(self, active_dir: Path, repository):
        super().__init__()
        self.active_dir = active_dir
        self.repository = repository

    def run(self):
        """
        Start the library scan
        :return:
        """
        pass


    def scan(self) -> List[ModelRecord]:
        """
        Scan all model locations and look for all models in the library. New models are added to the
        library, existing models are updated, missing models are marked as such.
        """
        models_root = self.config.comfy_root / 'models'
        extra_dirs = read_extra_model_paths(self.config.extra_paths_yaml)
        active_dirs: List[Path] = [models_root] + extra_dirs

        logger.info('Scanning active model dirs: %s', active_dirs)
        active_paths = list(iter_model_files(active_dirs, self.config.model_extensions))
        inactive_paths = list(iter_model_files([self.config.inactive_root], self.config.model_extensions))

        seen_shas: Set[str] = set()

        # Active models
        for path in active_paths:
            metadata, metadata_path = self.ensure_model_metadata(models_root, path)
            if metadata is None:
                logger.warning(f'Cannot read or write metadata, skipping model {path}')
            tags = set(metadata.get('tags', []))
            name = metadata.get('model_name', path.stem)
            mtype = metadata.get('model_type', '')
            sha = metadata.get('sha256', '')

            rec = ModelRecord(
                sha256=sha,
                name=name,
                model_type=mtype,
                model_path=path,
                original_path=path,
                metadata_path=metadata_path,
                status='active',
                accessible=True,
                tags=tags,
            )
            self.repo.upsert_model(rec)
            seen_shas.add(sha)

        # Inactive models
        for path in inactive_paths:
            metadata, metadata_path = self.ensure_model_metadata(models_root, path)
            if metadata is None:
                logger.warning(f'Cannot read or write metadata, skipping model {path}')
            tags = set(metadata.get('tags', []))
            name = metadata.get('model_name', path.stem)
            mtype = metadata.get('model_type', '')
            sha = metadata.get('sha256', '')

            rec = ModelRecord(
                sha256=sha,
                name=name,
                model_type=mtype,
                model_path=path,
                original_path=path,
                metadata_path=metadata_path,
                status='active',
                accessible=True,
                tags=tags,
            )
            self.repo.upsert_model(rec)



            # original_path might have been stored earlier; reuse if present
            existing = self.repo.get_model_by_sha(sha)
            original_path = existing.original_path if existing else path

            mtype = model_type_from_path(models_root, original_path)

            rec = ModelRecord(
                sha256=sha,
                name=name,
                model_type=mtype,
                model_path=path,
                original_path=original_path,
                metadata_path=metadata_path,
                status='inactive',
                accessible=True,
                tags=tags,
            )
            self.repo.upsert_model(rec)
            seen_shas.add(sha)

        # Mark previously-known models that we didn't see this time as 'missing' / inaccessible
        for rec in self.repo.all_models():
            if rec.sha256 not in seen_shas:
                self.repo.update_status_and_path(rec.sha256, accessible=False, status='missing')

        return self.repo.all_models()

    def ensure_model_metadata(self, models_root: Path, model_path: Path) -> tuple[Optional[dict], Optional[Path]]:
        json_path = model_path.with_suffix('.metadata.json')
        mtype = self.model_type_from_path(models_root, model_path)
        if not json_path.exists():
            # if a metadata file does not exist, create it
            logger.info('Computing sha256 for %s', model_path)
            sha = compute_sha256(model_path)
            data = {'model_name': model_path.stem, 'tags': [], 'sha256': sha, 'model_type': mtype}
            try:
                json_path.write_text(json.dumps(data), encoding='utf-8')
                return data, json_path
            except Exception as exc:
                logger.warning('Failed to create metadata %s: %s', json_path, exc)
                return None, json_path
        try:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            # force model type to be present
            if 'model_type' not in data:
                data['model_type'] = mtype
            json_path.write_text(json.dumps(data), encoding='utf-8')
            return data, json_path
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to parse or update metadata %s: %s', json_path, exc)
            return None, json_path

    def model_type_from_path(self, models_root: Path, model_path: Path) -> str:
        """
        Determine model type as the path component directly under 'models'.
        Example: models/checkpoints/foo.safetensors -> 'checkpoints'
        """
        try:
            rel = model_path.relative_to(models_root)
        except ValueError:
            # Fallback: just use parent folder filename
            return model_path.parent.name
        parts = rel.parts
        raw_type = parts[0] if parts else ''
        return self.config.model_types.get(raw_type, raw_type)

    # --- selection --------------------------------------------------------

    def filter_by_tag_expr(self, expr: str) -> List[ModelRecord]:
        pred = make_tag_filter(expr)
        return [m for m in self.repo.all_models() if pred(m.tags)]

    def models_by_shas(self, shas: Sequence[str]) -> List[ModelRecord]:
        out = []
        for sha in shas:
            rec = self.repo.get_model_by_sha(sha)
            if rec:
                out.append(rec)
        return out

    # --- moving -----------------------------------------------------------

    def _inactive_path_for(self, rec: ModelRecord) -> Path:
        """
        Decide where in the inactive_root a model should live.

        For now we use:
            inactive_root / model_type / filename

        You can change this mapping to something more sophisticated later.
        """
        return self.config.inactive_root / rec.model_type / rec.model_path.filename

    def preview_move_to_inactive(self, recs: Sequence[ModelRecord]) -> List[tuple[Path, Path]]:
        moves = []
        for rec in recs:
            if rec.status != 'active':
                continue
            dest = self._inactive_path_for(rec)
            moves.append((rec.model_path, dest))
        return moves

    def preview_move_to_active(self, recs: Sequence[ModelRecord]) -> List[tuple[Path, Path]]:
        moves = []
        for rec in recs:
            if rec.status != 'inactive':
                continue
            dest = rec.original_path
            moves.append((rec.model_path, dest))
        return moves

    def apply_moves(self, moves: Sequence[tuple[Path, Path]]) -> None:
        """
        Physically move models and update DB. Attachments should be handled here too.
        """
        for src, dest in moves:
            if not src.exists():
                logger.warning('Source missing, skipping: %s', src)
                continue
            if dest.exists():
                raise FileExistsError(f'Destination already exists: {dest}')

            dest.parent.mkdir(parents=True, exist_ok=True)
            logger.info('Moving %s -> %s', src, dest)
            shutil.move(str(src), str(dest))

        # After moving, rescan for simplicity
        self.rescan()