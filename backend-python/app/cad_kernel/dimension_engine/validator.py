class DimensionValidator:
    def score(self,dims):
        if not dims: return 0.0
        return min(1.0,len(dims)/10.0)
