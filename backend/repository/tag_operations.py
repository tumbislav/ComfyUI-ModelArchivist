# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tag_operations.py
# purpose: Tag usage and simultaneous remapping with recoverable file updates
# ---------------------------------------------------------------------------

import os
import json
from pathlib import Path
import tempfile

from sqlmodel import Session, select
from sqlalchemy import func

from backend.repository.tables import Tag, Model, Workflow, UserDefinedObject, Collection, ComponentType
from backend.repository.tables import TagModelLink, TagWorkflowLink, TagUserObjectLink, TagCollectionLink
from backend.files.metadata import ARCHIVIST_METADATA_SUFFIX
from backend.tags import normalize_tag


def tag_usage(engine) -> list[dict]:
    with Session(engine) as session:
        counts = {}
        for name, link in (('models', TagModelLink), ('workflows', TagWorkflowLink),
                           ('user_objects', TagUserObjectLink), ('collections', TagCollectionLink)):
            counts[name] = dict(session.exec(select(link.tag, func.count()).group_by(link.tag)).all())
        return [
            {'tag': tag.tag, **{name: values.get(tag.tag, 0) for name, values in counts.items()}}
            for tag in session.exec(select(Tag).order_by(Tag.tag)).all()
        ]


def _replace_bytes(path: Path, contents: bytes, mode: int) -> None:
    """Replace one file without exposing truncated JSON to readers."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.archivist-tags-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def prepare_tag_files(changes) -> list:
    files = {}
    for item, tags in changes:
        if not isinstance(item, (Model, Workflow)):
            continue
        for component_set in item.component_sets:
            found = False
            for component in component_set.components:
                if isinstance(item, Model):
                    if (component.component_type != ComponentType.METADATA or
                            not component.file_name.endswith(ARCHIVIST_METADATA_SUFFIX)):
                        continue
                elif component.component_type != ComponentType.WORKFLOW:
                    continue
                found = True
                path = Path(component.file_dir) / component.file_name
                if path.is_symlink() or not os.access(path, os.W_OK) or not os.access(path.parent, os.W_OK):
                    raise OSError(f'Metadata is not writable: {path}')
                original = path.read_bytes()
                stat = path.stat()
                data = json.loads(original)
                if not isinstance(data, dict):
                    raise ValueError(f'Metadata must be an object: {path}')
                metadata = data if isinstance(item, Model) else data.setdefault('config', {})
                if not isinstance(metadata, dict):
                    raise ValueError(f'Invalid workflow config: {path}')
                metadata['tags'] = tags
                updated = json.dumps(data, ensure_ascii=False).encode('utf-8')
                if path in files:
                    if files[path][2] != updated:
                        raise ValueError(f'Conflicting metadata updates: {path}')
                    files[path][4].append(component)
                else:
                    files[path] = (path, original, updated, stat, [component])
            if not found:
                raise ValueError(f'No writable metadata component for {item.id} on side {component_set.where}')
    return list(files.values())


def remap_tags(engine, mappings: dict[str, str], read_only: bool, prepare_files=prepare_tag_files,
               report=lambda progress: None) -> dict:
    """Apply one-step substitutions; roll back DB and restore files on execution failure."""
    result = {'applied': [], 'skipped': [], 'errors': []}
    if read_only:
        result['errors'].append({'code': 'read_only', 'message': 'Repository is read-only.'})
        return result

    with Session(engine) as session:
        known = {tag.tag: tag for tag in session.exec(select(Tag)).all()}
        replacements = {}
        for source, target in mappings.items():
            normalized = normalize_tag(target)
            code = None
            if not target:
                code = 'blank_target'
            elif normalized is None:
                code = 'invalid_tag'
            elif source not in known:
                code = 'unknown_tag'
            elif source == normalized:
                code = 'unchanged'
            if code:
                result['skipped'].append({'source': source, 'code': code,
                                           'message': f'{source}: {code.replace("_", " ")}.'})
            else:
                replacements[source] = normalized
        if not replacements:
            return result

        changes = []
        for kind in (Model, Workflow, UserDefinedObject, Collection):
            for item in session.exec(select(kind).where(kind.tags.any(Tag.tag.in_(replacements)))).all():
                blocked = item.summary()['read_only'] if isinstance(item, Collection) else item.read_only
                if blocked:
                    result['errors'].append({'code': 'object_read_only',
                                               'message': f'{kind.__name__} {item.id} is read-only.'})
                    continue
                original = {tag.tag for tag in item.tags}
                updated = sorted({replacements.get(tag, tag) for tag in original})
                if set(updated) != original:
                    changes.append((item, updated))
        if result['errors']:
            return result

        written = []
        try:
            report({'phase': 'preflight', 'objects_total': len(changes)})
            files = prepare_files(changes)
            for target in set(replacements.values()):
                if target not in known:
                    known[target] = Tag(tag=target)
                    session.add(known[target])

            # Remove links first so merges and swaps cannot violate compound keys.
            for item, updated in changes:
                item.tags = []
                session.add(item)
            session.flush()
            for item, updated in changes:
                item.tags = [known[tag] for tag in updated]
            session.flush()

            for index, entry in enumerate(files):
                path, original, updated, stat, components = entry
                if path.read_bytes() != original:
                    raise OSError(f'File changed during remap: {path}')
                written.append(entry)
                _replace_bytes(path, updated, stat.st_mode)
                refreshed = path.stat()
                for component in components:
                    component.size = refreshed.st_size
                    component.modified_at_ns = refreshed.st_mtime_ns
                    session.add(component)
                report({'phase': 'writing', 'files_completed': index + 1, 'files_total': len(files)})

            session.flush()
            for source in replacements:
                unused = session.exec(select(Tag).where(
                    Tag.tag == source, ~Tag.models.any(), ~Tag.workflows.any(),
                    ~Tag.user_objects.any(), ~Tag.collections.any())).first()
                if unused is not None:
                    session.delete(unused)
            session.commit()
            result['applied'] = list(replacements)
        except Exception as error:
            session.rollback()
            result['errors'].append({'code': 'remap_failed', 'message': str(error)})
            for path, original, updated, stat, components in reversed(written):
                try:
                    _replace_bytes(path, original, stat.st_mode)
                    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                except OSError as restore_error:
                    result['errors'].append({'code': 'restore_failed',
                                               'message': f'{path}: {restore_error}'})
        return result
