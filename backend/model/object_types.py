# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: enums.py
# purpose: Declarations of enum types
# ---------------------------------------------------------------------------

from enum import Enum

class ArchivistError(Enum):
    """
    Errors codes
    """
    INACCESSIBLE = 'Inaccessible folder'
    MODEL_MISSING = 'Missing model file'
    INCOMPLETE = 'Incomplete model'
    DUPLICATE_MODEL = 'Duplicate model hash'
    DUPLICATE_ARCHIVE = 'Duplicate archive location'
    MULTIPLE_PATHS_PER_TYPE = 'Multiple extra paths per type are not supported'
    INCONSISTENT_FILENAME = 'Model files have different names'


class ArchivistException(Exception):
    def __init__(self, error_code: ArchivistError, message: str):
        super().__init__()
        self.message = message
        self.code = error_code

    def __str__(self):
        return f'{self.code}: {self.message}'

class ComponentType(str, Enum):
    MODEL = 'model'
    METADATA = 'metadata'
    TITLE = 'title'
    EXTRA = 'extra'
    EXAMPLE = 'example'
    WORKFLOW = 'workflow'

