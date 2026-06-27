class DimensionPlacement:
    def arrange(self,dims):
        for i,d in enumerate(dims):
            d['x']=i*200; d['y']=0
        return dims
