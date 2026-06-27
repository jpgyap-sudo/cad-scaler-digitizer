class OcclusionHeuristics:
    def apply(self, edges):
        # Simplified heuristic:
        # If two edges share a source role and one has lower depth, keep the closer one visible.
        # Full 3D hidden-line removal can be implemented later using face projection.
        return edges
