"""DXF auditor — validates output before serving to user."""
import ezdxf


def audit_dxf(doc) -> dict:
    """
    Run comprehensive audit on DXF document.
    Returns dict with warnings, errors, and score.
    """
    result = {
        'errors': [],
        'warnings': [],
        'entity_counts': {},
        'score': 1.0,
        'layer_0_entities': 0,
    }

    # Count entities
    for e in doc.modelspace():
        et = e.dxftype()
        result['entity_counts'][et] = result['entity_counts'].get(et, 0) + 1
        if e.dxf.layer == '0':
            result['layer_0_entities'] += 1
            result['warnings'].append(f"Entity {et} on layer 0")

    # Check for zero-length lines
    for e in doc.modelspace():
        if e.dxftype() == 'LINE':
            start = e.dxf.start
            end = e.dxf.end
            if start.distance(end) < 0.01:
                result['errors'].append("Zero-length LINE detected")

    # Check for zero-radius circles
    for e in doc.modelspace():
        if e.dxftype() == 'CIRCLE' and e.dxf.radius < 0.01:
            result['errors'].append("Zero-radius CIRCLE detected")

    # Run ezdxf built-in audit
    auditor = doc.audit()
    if auditor.has_errors:
        result['errors'].extend(str(e) for e in auditor.errors)

    # Calculate quality score
    total_entities = sum(result['entity_counts'].values())
    if total_entities == 0:
        result['score'] = 0.0
    else:
        deduction = 0.0
        deduction += len(result['errors']) * 0.1
        deduction += result['layer_0_entities'] / max(total_entities, 1) * 0.2
        if not any('LWPOLYLINE' in k for k in result['entity_counts']):
            deduction += 0.3
        result['score'] = max(0.0, min(1.0, 1.0 - deduction))

    return result


def validate_dxf_file(filepath: str) -> dict:
    """Load and audit a DXF file."""
    try:
        doc = ezdxf.readfile(filepath)
        return audit_dxf(doc)
    except Exception as e:
        return {'errors': [str(e)], 'warnings': [], 'score': 0.0}
