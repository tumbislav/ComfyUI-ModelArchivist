# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: workflow_files.py
# purpose: Update workflow JSON metadata and file names
# ---------------------------------------------------------------------------

import json
from pathlib import Path

from backend.repository.tables import ComponentType, Workflow


def update_workflow(workflow: Workflow, file_name: str, internal_name: str,
                    purpose: str, tags: list[str]) -> None:
    """Update each deployed JSON copy and optionally rename it."""
    updates = []
    for component_set in workflow.component_sets:
        for component in component_set.components:
            if component.component_type != ComponentType.WORKFLOW:
                continue
            old_path = Path(component.file_dir) / component.file_name
            data = json.loads(old_path.read_text(encoding='utf-8'))
            config = data.setdefault('config', {})
            if not isinstance(config, dict):
                raise ValueError(f'invalid workflow config in {old_path}')
            config['name'] = internal_name
            config['purpose'] = purpose
            config['tags'] = tags
            new_path = old_path.with_name(f'{file_name}{old_path.suffix}')
            if new_path != old_path and new_path.exists():
                raise FileExistsError(new_path)
            updates.append((component, old_path, new_path, data))

    for component, old_path, new_path, data in updates:
        old_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        if new_path != old_path:
            old_path.rename(new_path)
            component.file_name = new_path.name
        stat = new_path.stat()
        component.size = stat.st_size
        component.modified_at_ns = stat.st_mtime_ns
