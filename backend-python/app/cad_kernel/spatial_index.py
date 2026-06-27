class SpatialIndex:
    def __init__(self):
        self.items = []

    def build(self, entities):
        self.items = []
        for e in entities:
            bbox = e.bbox() if hasattr(e, "bbox") else None
            if bbox:
                self.items.append((bbox, e.id))
        return self

    def query_bbox(self, bbox):
        x1, y1, x2, y2 = bbox
        hits = []
        for b, eid in self.items:
            bx1, by1, bx2, by2 = b
            if not (bx2 < x1 or bx1 > x2 or by2 < y1 or by1 > y2):
                hits.append(eid)
        return hits
