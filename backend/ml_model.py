"""
Prediction: "how long until the filter clogs?"

The differential pressure grows roughly exponentially, so ln(pressure) grows
linearly with time. We fit a linear regression on ln(pressure_drop) vs elapsed
seconds and extrapolate to the clog threshold. Learning the degradation rate
from data (rather than reading it from the simulator) means the same model
works on real sensor readings too.

Only the current filter cycle is used: a replaced filter (or a restarted
simulator) makes the pressure collapse, and mixing the old cycle's high values
with the new cycle's low ones would ruin the fit. Once the threshold is
crossed the filter is reported as clogged, with the fit made on the readings
from before the crossing.
"""

import math
import os

import numpy as np
from sklearn.linear_model import LinearRegression

CLOG_THRESHOLD_BAR = float(os.getenv("CLOG_THRESHOLD_BAR", "1.5"))
MIN_POINTS_FOR_FIT = 5
# A new cycle starts when the pressure drops by more than this between two
# readings (filter replaced; the sensor noise is +-0.02 bar) or when the data
# stops for longer than the gap below (the simulator restarts from a new filter).
CYCLE_RESET_DROP_BAR = 0.3
CYCLE_RESET_GAP_SECONDS = 600


def current_cycle(points: list) -> list:
    """points: [(time, pressure)] sorted by time -> the points since the last reset."""
    start = 0
    for i in range(1, len(points)):
        dropped = points[i - 1][1] - points[i][1] > CYCLE_RESET_DROP_BAR
        gap = (points[i][0] - points[i - 1][0]).total_seconds() > CYCLE_RESET_GAP_SECONDS
        if dropped or gap:
            start = i
    return points[start:]


class FilterPredictor:
    def __init__(self, clog_threshold_bar: float = CLOG_THRESHOLD_BAR):
        self.clog_threshold_bar = clog_threshold_bar

    def _fit(self, points: list):
        """Fit ln(pressure) = k*t + b; returns (slope, intercept, r2, t0, xs) or None."""
        points = [(t, p) for t, p in points if p > 0]
        if len(points) < MIN_POINTS_FOR_FIT:
            return None
        t0 = points[0][0]
        xs = np.array([[(t - t0).total_seconds()] for t, _ in points])
        log_ys = np.log(np.array([p for _, p in points]))
        model = LinearRegression().fit(xs, log_ys)
        r2 = float(model.score(xs, log_ys))
        return model.coef_[0], model.intercept_, r2, t0, xs

    def predict_days_remaining(self, readings: list) -> dict:
        points = sorted(
            (r["time"], float(r["pressure_drop_bar"]))
            for r in readings
            if r.get("pressure_drop_bar") is not None and r.get("time") is not None
        )
        base = {"clog_threshold_bar": self.clog_threshold_bar}
        if not points:
            return {**base, "status": "insufficient_data", "days_remaining": None,
                    "message": "No readings in the selected window."}

        cycle = current_cycle(points)
        latest_t, latest_p = cycle[-1]
        base.update({
            "current_pressure_bar": round(latest_p, 3),
            "cycle_started_at": cycle[0][0].isoformat(),
            "cycle_points": len(cycle),
        })

        # Already clogged: report since when, and how well the rise was modelled
        if latest_p >= self.clog_threshold_bar:
            idx = next(i for i, (_, p) in enumerate(cycle) if p >= self.clog_threshold_bar)
            clogged_at = cycle[idx][0]
            result = {
                **base,
                "status": "clogged",
                "days_remaining": 0.0,
                "seconds_remaining": 0.0,
                "clogged_at": clogged_at.isoformat(),
                "seconds_since_clogged": round((latest_t - clogged_at).total_seconds(), 1),
            }
            fit = self._fit(cycle[:idx])
            if fit is not None:
                slope, _, r2, _, xs = fit
                result.update({
                    "degradation_rate_per_hour": round(slope * 3600, 6),
                    "r_squared": round(r2, 4),
                    "points_used": int(len(xs)),
                })
            return result

        fit = self._fit(cycle)
        if fit is None:
            return {**base, "status": "insufficient_data", "days_remaining": None,
                    "message": f"Need at least {MIN_POINTS_FOR_FIT} readings in the current cycle."}

        slope, intercept, r2, t0, xs = fit
        if slope <= 0:
            return {**base, "status": "stable", "days_remaining": None,
                    "message": "Pressure shows no upward trend; the filter looks stable.",
                    "degradation_rate_per_hour": round(slope * 3600, 6),
                    "r_squared": round(r2, 4), "points_used": int(len(xs))}

        # solve exp(slope * t + intercept) = threshold  ->  t
        t_threshold = (math.log(self.clog_threshold_bar) - intercept) / slope
        seconds_remaining = max(t_threshold - (latest_t - t0).total_seconds(), 0)
        return {
            **base,
            "status": "ok",
            "days_remaining": round(seconds_remaining / 86400, 4),
            "seconds_remaining": round(float(seconds_remaining), 1),
            "degradation_rate_per_hour": round(slope * 3600, 6),
            "r_squared": round(r2, 4),
            "points_used": int(len(xs)),
        }
