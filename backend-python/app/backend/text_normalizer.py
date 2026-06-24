"""Normalize text labels in DXF — fix O to Ø, clean up duplicates."""
import re


def normalize_dimension_text(text: str) -> str:
    """Fix common OCR/CAD text issues."""
    if not text:
        return text
    # O80 → Ø80
    text = re.sub(r'\bO(\d+)\s*cm', r'Ø\1 cm', text)
    text = re.sub(r'\bO(\d+)\s*mm', r'Ø\1 mm', text)
    # DIA 80 → Ø80
    text = re.sub(r'DIA\s*(\d+)', r'Ø\1', text, flags=re.I)
    # DIAMETER 80 → Ø80
    text = re.sub(r'DIAMETER\s*(\d+)', r'Ø\1', text, flags=re.I)
    # H 70 → H=70
    text = re.sub(r'\bH\s+(\d+)', r'H=\1', text)
    # W 120 → W=120
    text = re.sub(r'\bW\s+(\d+)', r'W=\1', text)
    # Fix spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def remove_duplicate_labels(texts: list) -> list:
    """Remove duplicate or near-duplicate text labels."""
    seen = set()
    unique = []
    for t in texts:
        normalized = t.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(t)
    return unique


def clean_text_for_dxf(text: str) -> str:
    """Prepare text for DXF insertion — strip whitespace, fix encoding."""
    text = text.replace('\u00d8', 'Ø')  # Ensure Ø is correct unicode
    text = text.replace('Oslash', 'Ø')
    return text.strip()
