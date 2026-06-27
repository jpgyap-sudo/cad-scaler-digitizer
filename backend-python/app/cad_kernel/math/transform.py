from __future__ import annotations
from pydantic import BaseModel
from app.cad_kernel.math.vector import Vec3


class Transform(BaseModel):
    translation: Vec3 = Vec3()
    rotation_deg: float = 0
    scale: Vec3 = Vec3(x=1, y=1, z=1)

    def translated(self, x=0, y=0, z=0) -> "Transform":
        return Transform(
            translation=self.translation.add(Vec3(x=x, y=y, z=z)),
            rotation_deg=self.rotation_deg,
            scale=self.scale,
        )
