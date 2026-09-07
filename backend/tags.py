# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tags.py
# purpose: Canonical tag validation and browser identifier rules
# ---------------------------------------------------------------------------

from functools import lru_cache
import sys
import unicodedata

from backend.exception import ArcException


def normalize_tag(value: object) -> str | None:
    """Allow name characters, leading ASCII digits, spaces, and internal ASCII ':'/'-'."""
    if not isinstance(value, str):
        return None
    value = value.rstrip(' ')
    if not value or not (value[0].isidentifier() or value[0] in '0123456789'):
        return None
    if value[-1] in ':-':
        return None
    identifier = value.translate(str.maketrans({' ': '_', ':': '_', '-': '_'}))
    if not ('A' + identifier).isidentifier():
        return None
    return unicodedata.normalize('NFKC', value)


def edited_tags(values: object, existing=()) -> list[str]:
    """Validate newly assigned tags while retaining unchanged legacy spellings."""
    if not isinstance(values, list):
        raise ArcException(ArcException.Code.INVALID_TAG, 'Tags must be a list of strings')
    retained = set(existing)
    result = []
    for value in values:
        normalized = value if isinstance(value, str) and value in retained else normalize_tag(value)
        if normalized is None:
            raise ArcException(ArcException.Code.INVALID_TAG, f'Invalid tag: {value!r}')
        if normalized not in result:
            result.append(normalized)
    return result


@lru_cache(maxsize=1)
def browser_tag_rules() -> dict:
    """Export the running Python version's XID sets instead of trusting browser Unicode versions."""
    def character_class(predicate):
        ranges = []
        start = end = None
        for point in range(sys.maxunicode + 1):
            if predicate(chr(point)):
                if start is None:
                    start = point
                end = point
            elif start is not None:
                ranges.append((start, end))
                start = end = None
        if start is not None:
            ranges.append((start, end))
        return ''.join(f'\\u{{{first:x}}}' if first == last else
                       f'\\u{{{first:x}}}-\\u{{{last:x}}}' for first, last in ranges)

    start = character_class(lambda char: char.isidentifier() or char in '0123456789')
    continuation = character_class(lambda char: ('A' + char).isidentifier())
    return {'pattern': f'^[{start}](?:[{continuation} :\\-]*[{continuation}])?(?![\\s\\S])',
            'unicode_version': unicodedata.unidata_version}
