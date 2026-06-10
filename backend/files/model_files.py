# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: model_files.py
# purpose: File operations for models
# ---------------------------------------------------------------------------

import logging
from pathlib import Path
from backend.repository.tables import Model, ComponentType, DeploymentStatus
import json

logger = logging.getLogger('archivist.files')

renamed_file = lambda old_path, new_stem: str(old_path.parent / ''.join([new_stem] + old_path.suffixes))

def update_model(model: Model, name: str, internal_name: str, tags: list[str]):
    """
    Update a model's metadata and possibly rename the model files.
    """
    rename_files = model.name != name
    change_metadata = model.internal_name != internal_name or model.tags != tags or rename_files
    for c in model.components:
        if c.component_type == ComponentType.EXAMPLE:
            continue
        file_path = Path(c.file_dir) / c.file_name
        if file_path.name.endswith('metadata.json') and change_metadata:
            metadata = json.loads(file_path.read_text(encoding='utf-8'))
            metadata['tags'] = tags
            metadata['model_name'] = internal_name
            metadata['file_name'] = name
            if 'file_path' in metadata:
                metadata['file_path'] = renamed_file(Path(metadata['file_path']), name).replace('\\', '/')
            if 'preview_url' in metadata:
                metadata['preview_url'] = renamed_file(Path(metadata['preview_url']), name).replace('\\', '/')
            file_path.write_text(json.dumps(metadata, ensure_ascii=True), encoding='utf-8')
        if rename_files:
            file_path.rename(renamed_file(file_path, name))

def move_model(model: Model, deployment: DeploymentStatus) -> Model:
    """
    Move all of a model's components to the requested deployment. Update metadata as needed.
    """
    # Path().move works across filesystems
    pass

def sync_model(model: Model) -> Model:
    """
    Sync a model's components to both deployment locations.
    """
    pass
