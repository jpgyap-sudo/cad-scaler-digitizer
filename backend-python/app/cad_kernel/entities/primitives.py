from __future__ import annotations
from typing import List
from app.cad_kernel.entities.base import BaseEntity
from app.cad_kernel.math.vector import Vec2, Vec3


class LineEntity(BaseEntity):
    entity_type: str = "line"
    start: Vec2
    end: Vec2

    def bbox(self):
        return (min(self.start.x, self.end.x), min(self.start.y, self.end.y), max(self.start.x, self.end.x), max(self.start.y, self.end.y))


class PolylineEntity(BaseEntity):
    entity_type: str = "polyline"
    points: List[Vec2]
    closed: bool = False

    def bbox(self):
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))


class CircleEntity(BaseEntity):
    entity_type: str = "circle"
    center: Vec2
    radius: float

    def bbox(self):
        return (self.center.x - self.radius, self.center.y - self.radius, self.center.x + self.radius, self.center.y + self.radius)


class RectangleEntity(BaseEntity):
    entity_type: str = "rectangle"
    center: Vec2
    width: float
    height: float

    def corners(self):
        w, h = self.width / 2, self.height / 2
        return [
            Vec2(x=self.center.x - w, y=self.center.y - h),
            Vec2(x=self.center.x + w, y=self.center.y - h),
            Vec2(x=self.center.x + w, y=self.center.y + h),
            Vec2(x=self.center.x - w, y=self.center.y + h),
        ]

    def bbox(self):
        return (self.center.x - self.width/2, self.center.y - self.height/2, self.center.x + self.width/2, self.center.y + self.height/2)


class TextEntity(BaseEntity):
    entity_type: str = "text"
    insert: Vec2
    text: str
    height: float = 35

    def bbox(self):
        return (self.insert.x, self.insert.y, self.insert.x + len(self.text) * self.height * 0.6, self.insert.y + self.height)


class BoxEntity(BaseEntity):
    entity_type: str = "box"
    center: Vec3
    length: float
    depth: float
    height: float


class CylinderEntity(BaseEntity):
    entity_type: str = "cylinder"
    center: Vec3
    diameter: float
    height: float
