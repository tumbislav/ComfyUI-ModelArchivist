# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: base_models.py
# purpose: Normalize base-model metadata and produce compact abbreviations
# ---------------------------------------------------------------------------

import re


# Adapted from ComfyUI-Lora-Manager's BASE_MODEL_ABBREVIATIONS table.
# See ATTRIBUTIONS.md for source and license details.
BASE_MODEL_ABBREVIATIONS = {
    'SD 1.4': 'SD1', 'SD 1.5': 'SD1', 'SD 1.5 LCM': 'SD1',
    'SD 1.5 Hyper': 'SD1', 'SD 2.0': 'SD2', 'SD 2.1': 'SD2',
    'SD 3': 'SD3', 'SD 3.5': 'SD3', 'SD 3.5 Medium': 'SD3',
    'SD 3.5 Large': 'SD3', 'SD 3.5 Large Turbo': 'SD3',
    'SDXL 1.0': 'XL', 'SDXL Lightning': 'XL', 'SDXL Hyper': 'XL',
    'Flux.1 D': 'F1D', 'Flux.1 S': 'F1S', 'Flux.1 Krea': 'F1KR',
    'Flux.1 Kontext': 'F1KX', 'Flux.2 D': 'F2D',
    'Flux.2 Klein 9B': 'FK9', 'Flux.2 Klein 9B-base': 'FK9B',
    'Flux.2 Klein 4B': 'FK4', 'Flux.2 Klein 4B-base': 'FK4B',
    'SVD': 'SVD', 'LTXV': 'LTXV', 'LTXV2': 'LTV2', 'LTXV 2.3': 'LTX',
    'CogVideoX': 'CVX', 'Mochi': 'MCHI', 'Wan Video': 'WAN',
    'Wan Video 1.3B t2v': 'WAN', 'Wan Video 14B t2v': 'WAN',
    'Wan Video 14B i2v 480p': 'WAN', 'Wan Video 14B i2v 720p': 'WAN',
    'Wan Video 2.2 TI2V-5B': 'WAN', 'Wan Video 2.2 T2V-A14B': 'WAN',
    'Wan Video 2.2 I2V-A14B': 'WAN', 'Wan Video 2.5 T2V': 'WAN',
    'Wan Video 2.5 I2V': 'WAN', 'Hunyuan Video': 'HYV',
    'AuraFlow': 'AF', 'Chroma': 'CHR', 'PixArt a': 'PXA', 'PixArt E': 'PXE',
    'Hunyuan 1': 'HY', 'Lumina': 'L', 'Kolors': 'KLR', 'NoobAI': 'NAI',
    'Illustrious': 'IL', 'Pony': 'PONY', 'Pony V7': 'PNY7',
    'HiDream': 'HID', 'Qwen': 'QWEN', 'ZImageTurbo': 'ZIT',
    'ZImageBase': 'ZIB', 'Anima': 'ANI', 'ACE Audio': 'ACE',
    'Boogu': 'BOOG', 'Ernie': 'ERNI', 'Ernie Turbo': 'ETRB', 'Grok': 'GROK',
    'HappyHorse': 'HAPP', 'HiDream-O1': 'HIO1', 'Ideogram 4.0': 'ID40',
    'Krea 2': 'KR2', 'Lens': 'LENS', 'MAI': 'MAI', 'Nucleus': 'NUCL',
    'Qwen 2': 'QWN2', 'Upscaler': 'UPSC', 'Wan Image 2.7': 'WI27',
    'Wan Video 2.7': 'WAN', 'Other': 'OTH',
}

_NORMALIZED_ABBREVIATIONS = {
    name.casefold(): abbreviation
    for name, abbreviation in BASE_MODEL_ABBREVIATIONS.items()
}


def normalize_base_model(value: object) -> str:
    """Return a safe canonical value while preserving unknown model families."""
    return value.strip() if isinstance(value, str) else ''


def abbreviate_base_model(value: object) -> str:
    """Return a compact display abbreviation for a full base-model name."""
    base_model = normalize_base_model(value)
    if not base_model:
        return ''
    normalized = base_model.casefold()
    if 'wan video' in normalized:
        return 'WAN'
    if abbreviation := _NORMALIZED_ABBREVIATIONS.get(normalized):
        return abbreviation
    tokens = [token for token in re.split(r'[\s_-]+', base_model) if token]
    initialism = ''.join(token[0] for token in tokens)[:4]
    if len(initialism) >= 2:
        return initialism.upper()
    alphanumeric = ''.join(character for character in base_model
                           if character.isascii() and character.isalnum())
    return alphanumeric[:4].upper() if alphanumeric else 'OTH'
