"""
Prediction: "how long until the filter clogs?"

The filter's hydraulic resistance grows exponentially as it clogs. In series
with the rest of the plumbing, fed at the mains supply pressure P_s, the
pressure drop across it is p = P_s * x / (1 + x), with x = R_filter / R_system
= x0 * e^(k*t). Inverting: x = p / (P_s - p), so

    ln( p / (P_s - p) ) = ln(x0) + k*t          -> linear in time

We fit a linear regression on that transform vs elapsed seconds and solve for
the time the threshold is reached. Early on (p << P_s) this is the familiar
exponential rise of the pressure; near P_s it also captures the levelling off.
Learning k from data (rather than reading it from the simulator) means the same
model works on real sensor readings - P_s is the measured mains pressure.

Only the current filter cycle is used: a replaced filter (or a restarted
simulator) makes the pressure collapse, and mixing the old cycle's high values
with the new cycle's low ones would ruin the fit. Once the threshold is
crossed the filter is reported as clogged, with the fit made on the readings
from before the crossing.
"""

import os

import numpy as np
from sklearn.linear_model import LinearRegression

CLOG_THRESHOLD_BAR = float(os.getenv("CLOG_THRESHOLD_BAR", "1.5"))
SUPPLY_PRESSURE_BAR = float(os.getenv("SUPPLY_PRESSURE_BAR", "4.0"))
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
    def __init__(self, clog_threshold_bar: float = CLOG_THRESHOLD_BAR,
                 supply_pressure_bar: float = SUPPLY_PRESSURE_BAR):
        self.clog_threshold_bar = clog_threshold_bar
        self.supply_pressure = supply_pressure_bar

    def _linearize(self, p):
        """p -> ln(p / (P_s - p)) = ln(R_filter / R_system), linear in time."""
        return np.log(p / (self.supply_pressure - p))

    def _fit(self, points: list):
        """Fit ln(p/(P_s-p)) = k*t + b; returns (slope, intercept, r2, t0, xs) or None."""
        # the transform needs 0 < p < P_s; readings pinned at the ceiling carry no trend
        points = [(t, p) for t, p in points if 0 < p < 0.98 * self.supply_pressure]
        if len(points) < MIN_POINTS_FOR_FIT:
            return None
        t0 = points[0][0]
        xs = np.array([[(t - t0).total_seconds()] for t, _ in points])
        log_ys = self._linearize(np.array([p for _, p in points]))
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

        # solve slope * t + intercept = ln(threshold / (P_s - threshold))  ->  t
        t_threshold = (float(self._linearize(self.clog_threshold_bar)) - intercept) / slope
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
