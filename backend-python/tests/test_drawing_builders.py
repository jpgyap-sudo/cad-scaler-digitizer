"""Regression guard for DrawingModel builders.

Every build_*_model function must populate at least one renderable shape
(circle/polygon/line) in its views. A dataclass-field-order mistake (passing
positional args that land in the wrong field, e.g. `type`) silently produces
an empty model that renders as a blank SVG — this test catches that class of
bug before it ships.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.backend.drawing_builders import (
    build_round_pedestal_model, build_rectangular_table_model, build_cabinet_model,
    build_sofa_model, build_coffee_table_model, build_dining_chair_model,
    build_wardrobe_model, build_reception_counter_model, build_bed_headboard_model,
    build_generic_model,
)
from app.backend.svg_exporter import drawing_to_svg


def _shape_count(model):
    return sum(len(v.circles) + len(v.polygons) + len(v.lines) for v in model.views)


BUILDERS = [
    build_round_pedestal_model,
    build_rectangular_table_model,
    build_cabinet_model,
    build_sofa_model,
    build_coffee_table_model,
    build_dining_chair_model,
    build_wardrobe_model,
    build_reception_counter_model,
    build_bed_headboard_model,
]


def test_all_builders_produce_geometry():
    for builder in BUILDERS:
        model = builder()
        assert len(model.views) > 0, f"{builder.__name__} produced no views"
        assert _shape_count(model) > 0, f"{builder.__name__} produced an empty view (no shapes)"


def test_all_builders_render_to_nonempty_svg():
    for builder in BUILDERS:
        model = builder()
        svg = drawing_to_svg(model)
        shapes = svg.count('<circle') + svg.count('<polygon') + svg.count('<line') + svg.count('<rect')
        # >1 because the page border itself is one <rect>.
        assert shapes > 1, f"{builder.__name__} rendered an SVG with no real geometry"


def test_generic_model_traces_detected_geometry():
    lines = [((0, 0), (100, 0)), ((100, 0), (100, 50))]
    circles = [(50, 25, 10)]
    rects = [(10, 10, 90, 40)]
    model = build_generic_model(lines, circles, rects)
    assert _shape_count(model) == len(lines) + len(circles) + len(rects)


def test_generic_model_handles_no_geometry():
    model = build_generic_model()
    assert len(model.views) > 0
    drawing_to_svg(model)  # must not raise
