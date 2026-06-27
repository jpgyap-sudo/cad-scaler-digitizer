class QualityScorer:
    def score(self, issues, metrics):
        score=1.0
        for i in issues:
            if i.severity=="error":
                score-=0.20
            elif i.severity=="warning":
                score-=0.07
            else:
                score-=0.02
        return max(0.0,min(1.0,round(score,3)))
