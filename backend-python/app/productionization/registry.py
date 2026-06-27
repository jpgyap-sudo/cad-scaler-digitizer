from app.productionization.config import settings


class TemplateRegistry:
    def list_templates(self):
        return [
            {
                "id": "table.dual_cylindrical_pedestal.v1",
                "product_type": "dining_table",
                "name": "Dual Cylindrical Pedestal Table",
                "confidence": 0.85,
            },
            {
                "id": "casework.rectangular.v1",
                "product_type": "sideboard",
                "name": "Rectangular Casework",
                "confidence": 0.75,
            },
        ]


class ResourceRegistry:
    def list_resources(self):
        return [
            {"id": "geometry.table.rectangular_top", "category": "geometry", "confidence": 0.85},
            {"id": "support.table.dual_cylindrical_pedestal", "category": "support", "confidence": 0.82},
            {"id": "joinery.hidden_steel_frame", "category": "joinery", "confidence": 0.88},
        ]
