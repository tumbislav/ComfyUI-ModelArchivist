# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: object_types.py
# purpose: Declarations of complex object types that get passed around
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict
from enum import StrEnum


class Location(str, StrEnum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ARCHIVE = 'archive'

class ModelInLocation(BaseModel):
    location: Location | None
    sha256: str | None
    name: str | None
    tags: List[str]
    model_path: Path
    metadata_path: Path | None
    metadata: Dict
    relative_path: Path
    extra_files: List[Path]
    examples_dir: Path | None
    examples: List[Path]