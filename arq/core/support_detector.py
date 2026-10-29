"""Isolation Forest plus a robust training-support envelope.

Trees do not extrapolate beyond training split points. This optional candidate
also scores absolute deviation from normal training medians, scaled by IQR
with per-feature unit floors. Its threshold is learned on separate calibration
runs. This is a heuristic anomaly score, not a probability.
"""
class SupportAwareIsolationForest:
    def __init__(self, random_state=42):self.random_state=random_state

    def fit(self, data):
        import numpy as np
        from sklearn.ensemble import IsolationForest
        self.forest=IsolationForest(n_estimators=100,contamination=.05,random_state=self.random_state,n_jobs=1).fit(data)
        self.center=np.median(data,axis=0)
        self.scale=np.maximum(np.quantile(data,.75,axis=0)-np.quantile(data,.25,axis=0),[5,16,64,1,64,64,1])
        return self

    def decision_function(self,data):
        import numpy as np
        values=np.asarray(data,dtype=float)
        support=np.max(np.abs(values-self.center)/self.scale,axis=1)
        isolation=.5-self.forest.decision_function(values)
        return -np.maximum(support,isolation)
