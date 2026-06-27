class HiddenLineQualityScorer:
    def score(self, result):
        total = len(result.classified_edges)
        if total == 0:
            result.warnings.append("No edges classified.")
            result.quality_score = 0.0
            return result

        hidden = len([e for e in result.classified_edges if e.line_class == "hidden"])
        center = len([e for e in result.classified_edges if e.line_class == "centerline"])
        visible = len([e for e in result.classified_edges if e.line_class in ["visible", "silhouette"]])

        score = 0.65
        if visible:
            score += 0.15
        if hidden:
            score += 0.10
        if center:
            score += 0.10

        result.quality_score = min(1.0, score)
        return result
