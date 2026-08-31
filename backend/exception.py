# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: exception.py
# purpose: Exception handling
# ---------------------------------------------------------------------------

from enum import StrEnum


class ArcException(Exception):
    """
    Error codes
    """
    class Code(StrEnum):
        DATABASE_UNAVAILABLE = 'Database unavailable'
        INVALID_DATABASE = 'Invalid database'
        INACCESSIBLE_FOLDER = 'Inaccessible folder'
        INACCESSIBLE_FILE = 'Inaccessible file'
        READ_ONLY = 'Application is read-only'
        MISSING_MODEL_FILE = 'Missing model file'
        INCONSISTENT_FILENAME = 'Model files have different names'
        INCOMPLETE_MODEL = 'Incomplete model'
        DUPLICATE_MODEL = 'Duplicate model hash'
        UNKNOWN_MODEL = 'Model does not exist'
        UNKNOWN_WORKFLOW = 'Workflow does not exist'
        INVALID_USER_TYPE = 'Invalid user-defined type'
        UNKNOWN_USER_TYPE = 'User-defined type does not exist'
        UNKNOWN_USER_OBJECT = 'User-defined object does not exist'
        USER_TYPE_IN_USE = 'User-defined type has objects'
        CONFIRMATION_REQUIRED = 'Confirmation required'
        INVALID_CONFIRMATION = 'Invalid or expired confirmation'
        INVALID_COLLECTION = 'Invalid collection'
        EMPTY_COLLECTION = 'Collection cannot be empty'
        UNKNOWN_COLLECTION = 'Collection does not exist'
        DUPLICATE_COLLECTION_MEMBER = 'Duplicate collection member'
        COLLECTION_CYCLE = 'Collection membership cycle'

    def __init__(self, error_code: Code, message: str):
        super().__init__()
        self.message = message
        self.code = error_code

    def __str__(self):
        return f'{self.code}: {self.message}'
