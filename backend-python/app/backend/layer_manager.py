"""Layer manager — auto-create and validate DXF layers. No layer 0.

Standard layers follow common CAD conventions:
  OBJECT      — Visible object edges (main geometry outlines)
  DIMENSION   — Dimension lines, extension lines, dimension text
  LEADER      — Leader lines and callouts
  CENTERLINE  — Centerlines and symmetry axes
  HATCH       — Hatching and fills (wood grain, fabric, metal)
  MTEXT       — Multi-line text notes, callouts, labels
  HIDDEN      — Hidden lines, inferred/estimated geometry
  REFERENCE_IMAGE — Embedded or referenced source image boundary
  TITLE_BLOCK — Title block, border, revision table
"""

import ezdxf


STANDARD_LAYERS = {
    'OBJECT': {'color': 7, 'linetype': 'CONTINUOUS', 'description': 'Visible object edges and main outlines'},
    'DIMENSION': {'color': 3, 'linetype': 'CONTINUOUS', 'description': 'Dimension lines, extension lines, and dimension text'},
    'LEADER': {'color': 4, 'linetype': 'CONTINUOUS', 'description': 'Leader lines and callouts'},
    'CENTERLINE': {'color': 5, 'linetype': 'CENTER2', 'description': 'Centerlines and symmetry axes'},
    'HIDDEN': {'color': 251, 'linetype': 'HIDDEN', 'description': 'Hidden lines and inferred/estimated geometry'},
    'MTEXT': {'color': 2, 'linetype': 'CONTINUOUS', 'description': 'Multi-line text notes, callouts, labels'},
    'REFERENCE_IMAGE': {'color': 9, 'linetype': 'PHANTOM', 'description': 'Embedded or referenced source image boundary'},
    'HATCH': {'color': 8, 'linetype': 'CONTINUOUS', 'description': 'Hatching and fills (wood grain, fabric, metal)'},
    'TITLE_BLOCK': {'color': 6, 'linetype': 'CONTINUOUS', 'description': 'Title block, border, revision table'},
    # Legacy aliases kept for backward compatibility
    'OUTLINE': {'color': 7, 'linetype': 'CONTINUOUS', 'description': 'Visible object edges (legacy — use OBJECT)'},
    'DIMENSIONS': {'color': 3, 'linetype': 'CONTINUOUS', 'description': 'Dimension lines (legacy — use DIMENSION)'},
    'CENTERLINES': {'color': 5, 'linetype': 'CENTER2', 'description': 'Centerlines (legacy — use CENTERLINE)'},
    'ANNOTATIONS': {'color': 2, 'linetype': 'CONTINUOUS', 'description': 'Text notes (legacy — use MTEXT)'},
    'CENTER': {'color': 5, 'linetype': 'CENTER2', 'description': 'Centerlines (legacy)'},
    'TEXT': {'color': 2, 'linetype': 'CONTINUOUS', 'description': 'Text labels (legacy)'},
    'TITLE': {'color': 6, 'linetype': 'CONTINUOUS', 'description': 'Title block (legacy)'},
    'BORDER': {'color': 7, 'linetype': 'CONTINUOUS', 'description': 'Sheet border (legacy)'},
}

# Recommended layer names for new code (use these instead of legacy names)
RECOMMENDED_LAYERS = {
    'object': 'OBJECT',
    'dimension': 'DIMENSION',
    'leader': 'LEADER',
    'centerline': 'CENTERLINE',
    'hatch': 'HATCH',
    'mtext': 'MTEXT',
    'hidden': 'HIDDEN',
    'reference_image': 'REFERENCE_IMAGE',
    'title_block': 'TITLE_BLOCK',
}


def setup_layers(doc):
    """Add standard layers to a DXF document. Never uses layer 0.
    Creates both new recommended layers and legacy aliases for backward compatibility."""
    for name, props in STANDARD_LAYERS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name=name)
            layer.color = props['color']
            try:
                layer.dxf.linetype = props['linetype']
            except Exception:
                pass
    return doc


def validate_no_layer_0(doc) -> list:
    """Check all entities for layer 0 usage. Returns warnings."""
    warnings = []
    for entity in doc.modelspace():
        if entity.dxf.layer == '0':
            warnings.append(f"Entity {entity.dxftype()} on layer 0 (should use OBJECT or appropriate layer)")
    return warnings


def get_layer_color(layer_name: str) -> int:
    """Get standard color for a layer."""
    if layer_name in STANDARD_LAYERS:
        return STANDARD_LAYERS[layer_name]['color']
    return 7  # Default white


def layer_for_entity_type(entity_type: str, is_estimated: bool = False) -> str:
    """Map an entity type to the recommended DXF layer.
    Uses the modern layer naming convention (OBJECT, DIMENSION, etc.)."""
    if is_estimated:
        return 'HIDDEN'
    mapping = {
        'line': 'OBJECT',
        'circle': 'OBJECT',
        'arc': 'OBJECT',
        'polyline': 'OBJECT',
        'rectangle': 'OBJECT',
        'polygon': 'OBJECT',
        'dimension': 'DIMENSION',
        'dimension_line': 'DIMENSION',
        'extension_line': 'DIMENSION',
        'leader': 'LEADER',
        'centerline': 'CENTERLINE',
        'center': 'CENTERLINE',
        'text': 'MTEXT',
        'mtext': 'MTEXT',
        'label': 'MTEXT',
        'note': 'MTEXT',
        'hatch': 'HATCH',
        'fill': 'HATCH',
        'title': 'TITLE_BLOCK',
        'border': 'TITLE_BLOCK',
        'reference_image': 'REFERENCE_IMAGE',
    }
    return mapping.get(entity_type.lower(), 'OBJECT')
