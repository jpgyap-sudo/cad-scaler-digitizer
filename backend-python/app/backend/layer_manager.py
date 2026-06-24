"""Layer manager — auto-create and validate DXF layers. No layer 0."""
import ezdxf


STANDARD_LAYERS = {
    'OBJECT': {'color': 7, 'linetype': 'CONTINUOUS', 'description': 'Main geometry'},
    'DIMENSION': {'color': 3, 'linetype': 'CONTINUOUS', 'description': 'Dimensions'},
    'CENTER': {'color': 5, 'linetype': 'CENTER2', 'description': 'Centerlines'},
    'TEXT': {'color': 2, 'linetype': 'CONTINUOUS', 'description': 'Text labels'},
    'MTEXT': {'color': 2, 'linetype': 'CONTINUOUS', 'description': 'Multi-line text'},
    'HATCH': {'color': 8, 'linetype': 'CONTINUOUS', 'description': 'Hatching'},
    'HIDDEN': {'color': 251, 'linetype': 'HIDDEN', 'description': 'Hidden lines'},
    'TITLE': {'color': 6, 'linetype': 'CONTINUOUS', 'description': 'Title block'},
    'BORDER': {'color': 7, 'linetype': 'CONTINUOUS', 'description': 'Sheet border'},
}


def setup_layers(doc):
    """Add standard layers to a DXF document. Never uses layer 0."""
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
            warnings.append(f"Entity {entity.dxftype()} on layer 0")
    return warnings


def get_layer_color(layer_name: str) -> int:
    """Get standard color for a layer."""
    if layer_name in STANDARD_LAYERS:
        return STANDARD_LAYERS[layer_name]['color']
    return 7  # Default white
