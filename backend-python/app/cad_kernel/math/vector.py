from __future__ import annotations
from pydantic import BaseModel
import math


class Vec2(BaseModel):
    x: float = 0
    y: float = 0

    def add(self, other: "Vec2") -> "Vec2":
        return Vec2(x=self.x + other.x, y=self.y + other.y)

    def sub(self, other: "Vec2") -> "Vec2":
        return Vec2(x=self.x - other.x, y=self.y - other.y)

    def scale(self, s: float) -> "Vec2":
        return Vec2(x=self.x * s, y=self.y * s)

    def distance_to(self, other: "Vec2") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Vec3(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0

    def add(self, other: "Vec3") -> "Vec3":
        return Vec3(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)

    def scale(self, s: float) -> "Vec3":
        return Vec3(x=self.x * s, y=self.y * s, z=self.z * s)
