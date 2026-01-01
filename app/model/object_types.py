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

class ComponentType(str, Enum):
    MODEL = 'model'
    METADATA = 'metadata'
    TITLE = 'title'
    EXTRA = 'extra'
    WORKFLOW = 'workflow'

class ScanError(Enum):
    """
    Errors encountered during a file system scan
    """
    INACCESSIBLE = 'A registered folder is not accessible'
    MODEL_MISSING = 'Main model file is neither in the active nor in inactive location'
    INCOMPLETE = 'Part of the model is in active and part in inactive locations'
    ARCHIVE_INCOMPLETE = 'Some of the model components are archived, some not'
    DUPLICATES = 'Multiple models with the same sha256 value exist'
