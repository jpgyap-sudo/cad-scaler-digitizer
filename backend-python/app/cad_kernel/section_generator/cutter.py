class SectionCutter:
    def cut(self, scene, plane):
        nodes = scene.get("nodes", [])
        target_ids = set(plane.target_node_ids)
        return [n for n in nodes if n.get("id") in target_ids]
