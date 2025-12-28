# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: object_types.py
# purpose: Declarations of complex object types that get passed around
# ---------------------------------------------------------------------------

from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict
from enum import Enum


class Location(str, Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ARCHIVE = 'archive'

class ModelInLocation(BaseModel):
    location: Location | None
    type: str
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

class ScanErrors(Enum):
    """
    Errors encountered during a file system scan
    """
    INACCESSIBLE: "A registered folder is not accessible"
    MODEL_MISSING: "Main model file is neither in the active nor in inactive location"
    DISPERSED: "Part of the model is in active and part in inactive locations"
    ARCHIVE_INCOMPLETE: "Some of the model components are archivec, some not"