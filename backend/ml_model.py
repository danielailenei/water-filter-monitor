"""
Prediction: "how many days until the filter clogs?"

The differential pressure grows roughly exponentially, so ln(pressure) grows
linearly with time. We fit a linear regression on ln(pressure_drop) vs elapsed
seconds over the recent history and extrapolate to the clog threshold. Learning
the degradation rate from data (rather than reading it from the simulator) means
the same model works on real sensor readings too.
"""

import math
import os

import numpy as np
from sklearn.linear_model import LinearRegression

CLOG_THRESHOLD_BAR = float(os.getenv("CLOG_THRESHOLD_BAR", "1.5"))
MIN_POINTS_FOR_FIT = 5


class FilterPredictor:
    def __init__(self, clog_threshold_bar: float = CLOG_THRESHOLD_BAR):
        self.clog_threshold_bar = clog_threshold_bar

    def _prepare_series(self, readings: list):
        """Extract (elapsed_seconds, pressure_drop) arrays, sorted, pressure > 0."""
        points = [
            (r["time"], r["pressure_drop_bar"])
            for r in readings
            if r.get("pressure_drop_bar") is not None and r.get("time") is not None
        ]
        points.sort(key=lambda p: p[0])
        if len(points) < MIN_POINTS_FOR_FIT:
            return None, None

        t0 = points[0][0]
        xs = np.array([[(t - t0).total_seconds()] for t, _ in points])
        ys = np.array([p for _, p in points])

        mask = ys > 0
        if mask.sum() < MIN_POINTS_FOR_FIT:
            return None, None
        return xs[mask], ys[mask]

    def predict_days_remaining(self, readings: list) -> dict:
        xs, ys = self._prepare_series(readings)
        if xs is None:
            return {
                "status": "insufficient_data",
                "message": f"Need at least {MIN_POINTS_FOR_FIT} valid readings to predict.",
                "days_remaining": None,
            }

        log_ys = np.log(ys)
        model = LinearRegression()
        model.fit(xs, log_ys)

        slope = model.coef_[0]        # k, degradation rate (1/s)
        intercept = model.intercept_  # ln(base_pressure)
        latest_t = xs[-1][0]
        latest_pressure = float(np.exp(slope * latest_t + intercept))

        if slope <= 0:
            return {
                "status": "stable",
                "message": "Pressure shows no upward trend; the filter looks stable.",
                "days_remaining": None,
                "current_pressure_bar": round(latest_pressure, 3),
                "degradation_rate_per_hour": round(slope * 3600, 6),
            }

        # solve exp(slope * t + intercept) = threshold  ->  t
        t_threshold = (math.log(self.clog_threshold_bar) - intercept) / slope
        seconds_remaining = max(t_threshold - latest_t, 0)

        return {
            "status": "ok",
            "days_remaining": round(seconds_remaining / 86400, 2),
            "current_pressure_bar": round(latest_pressure, 3),
            "clog_threshold_bar": self.clog_threshold_bar,
            "degradation_rate_per_hour": round(slope * 3600, 6),
            "r_squared": round(float(model.score(xs, log_ys)), 4),
            "points_used": int(len(xs)),
        }
