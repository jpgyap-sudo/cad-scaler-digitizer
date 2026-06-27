from app.models import GenerateRequest
from app.jobs import JobService

request = GenerateRequest(
    product_id="HOMEU-TABLE-001",
    product_name="Dual Pedestal Dining Table",
    product_type_hint="dining_table",
    known_dimensions_mm={
        "length_mm": 1800,
        "depth_mm": 900,
        "height_mm": 750,
        "top_thickness_mm": 30,
    },
    material_hints={"top": "white_stone", "base": "matte_black_metal"},
)

job = JobService().create_and_run(request)
print(job.model_dump_json(indent=2))
