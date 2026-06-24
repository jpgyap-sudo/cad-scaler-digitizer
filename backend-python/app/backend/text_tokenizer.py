"""
Dynamic Text Tokenization Engine — Feed extracted dimensions through
a string sanitizer before writing to DXF. Maps variations like
"80cm DIA", "DIA 80", "O80", "diameter = 80" into %%c80 cm format.
"""
import re


# Mapping patterns: (regex, replacement_format)
DIMENSION_PATTERNS = [
    # "O80 cm" or "O 80 cm" → %%c80 cm
    (r'\bO\s*(\d+(?:\.\d+)?)\s*(cm|mm)?', r'%%c\1 \2'),
    # "DIA 80 cm" or "Dia 80" → %%c80 cm
    (r'\bDIA\w*\s*(\d+(?:\.\d+)?)\s*(cm|mm)?', r'%%c\1 \2', re.I),
    # "diameter = 80" or "diameter:80" → %%c80
    (r'\bdiameter\s*[=:]\s*(\d+(?:\.\d+)?)', r'%%c\1', re.I),
    # "H = 70 cm" or "h:70cm" → H=70 cm
    (r'\b[Hh]\s*[=:]\s*(\d+(?:\.\d+)?)\s*(cm|mm)?', r'H=\1 \2'),
    # "W : 120 cm" → W=120 cm
    (r'\b[Ww]\s*[=:]\s*(\d+(?:\.\d+)?)\s*(cm|mm)?', r'W=\1 \2'),
    # "D = 50 cm" → D=50 cm
    (r'\b[Dd](?:epth)?\s*[=:]\s*(\d+(?:\.\d+)?)\s*(cm|mm)?', r'D=\1 \2'),
]


def clean_dimension_string(raw_text: str) -> str:
    """
    Clean a raw OCR dimension text into CAD-compliant format.
    Examples:
    "O80 cm" → "%%c80 cm"
    "DIA 80" → "%%c80"
    "80cm DIA" → "%%c80 cm"
    "H=70cm" → "H=70 cm"
    """
    if not raw_text:
        return raw_text

    cleaned = raw_text.strip()

    for pattern, replacement, *flags in DIMENSION_PATTERNS:
        flag = flags[0] if flags else 0
        try:
            cleaned = re.sub(pattern, replacement, cleaned, flags=flag)
        except Exception:
            pass

    return cleaned


def extract_numeric_value(text: str) -> tuple:
    """
    Extract numeric value and unit from dimension text.
    Returns (value, unit, is_diameter).
    """
    value = 0.0
    unit = 'cm'
    is_diameter = False

    # Check for diameter indicators
    if any(s in text for s in ['%%c', 'DIA', 'diameter', 'O', 'Ø']):
        is_diameter = True

    # Extract number
    nums = re.findall(r'(\d+(?:\.\d+)?)', text)
    if nums:
        value = float(nums[0])

    # Extract unit
    unit_match = re.search(r'(cm|mm|m|in|ft)', text, re.I)
    if unit_match:
        unit = unit_match.group(1).lower()

    return value, unit, is_diameter


def format_dimension_for_dxf(value: float, unit: str = 'cm', is_diameter: bool = False) -> str:
    """Format a clean dimension string for DXF output."""
    if is_diameter:
        return f'%%c{value:g} {unit}'
    return f'{value:g} {unit}'


# Legacy mapping for backward compatibility
def apply_legacy_fixes(text: str) -> str:
    """Apply fixes for common OCR errors in dimension text."""
    text = text.replace('O0', '%%c')  # O0 → %%c
    text = re.sub(r'^O(\d)', r'%%c\1', text)  # O80 → %%c80
    text = re.sub(r'DIA\s*', '%%c', text, flags=re.I)
    return text
