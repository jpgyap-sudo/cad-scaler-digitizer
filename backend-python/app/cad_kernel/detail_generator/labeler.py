class DetailLabeler:
    def assign_labels(self, details):
        for i, d in enumerate(details):
            d.label = f"DETAIL {chr(65+i)}"
            d.scale = "1:2" if d.priority >= 80 else "1:5"
        return details
