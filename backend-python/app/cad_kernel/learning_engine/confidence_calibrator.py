class ConfidenceCalibrator:
    def calibrate(self,approved,current=0.85):
        return min(0.99,current+0.03) if approved else max(0.40,current-0.08)
