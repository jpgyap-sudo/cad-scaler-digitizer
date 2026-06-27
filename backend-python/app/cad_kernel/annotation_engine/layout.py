class AnnotationLayout:
    def arrange(self, anns):
        for i, a in enumerate(anns):
            a.anchor["y"] = a.anchor.get("y", 0) - i * 30
        return anns
