"""
Model de predictie: "in cate zile se va infunda filtrul?"

Abordare: presiunea diferentiala urmareste (conform filter_model.py din
senzor) o crestere aproximativ exponentiala in timp:

    pressure(t) = base_pressure * exp(k * t)

Ceea ce inseamna ca ln(pressure(t)) este LINIAR in raport cu t. Folosim
regresie liniara (scikit-learn) pe ln(pressure_drop) in functie de timpul
scurs, din istoricul real de citiri stocat in InfluxDB, extrapoland pana
la pragul de infundare (CLOG_THRESHOLD_BAR).

Avantajul acestei abordari fata de citirea directa a parametrului din
simulator: modelul invata rata de degradare direct din date, deci
functioneaza si daca alimentam sistemul cu citiri reale de la un senzor
fizic, nu doar cu date simulate.
"""

import math
from datetime import datetime, timezone

import numpy as np
from sklearn.linear_model import LinearRegression

CLOG_THRESHOLD_BAR = 1.5
MIN_POINTS_FOR_FIT = 5


class FilterPredictor:
    def __init__(self, clog_threshold_bar: float = CLOG_THRESHOLD_BAR):
        self.clog_threshold_bar = clog_threshold_bar

    def _prepare_series(self, readings: list):
        """Extrage (elapsed_seconds, pressure_drop) din citirile brute, sortate crescator."""
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

        # eliminam valori invalide (presiune <=0) inainte de log
        mask = ys > 0
        if mask.sum() < MIN_POINTS_FOR_FIT:
            return None, None

        return xs[mask], ys[mask]

    def predict_days_remaining(self, readings: list) -> dict:
        """
        readings: lista de dict-uri asa cum vin din DBWriter.get_recent_readings()
        Intoarce un dict cu predictia si metadate utile pentru debugging/raport.
        """
        xs, ys = self._prepare_series(readings)

        if xs is None:
            return {
                "status": "insufficient_data",
                "message": f"Sunt necesare cel putin {MIN_POINTS_FOR_FIT} citiri valide pentru predictie.",
                "days_remaining": None,
            }

        log_ys = np.log(ys)

        model = LinearRegression()
        model.fit(xs, log_ys)

        slope = model.coef_[0]          # k, rata de degradare (1/secunda)
        intercept = model.intercept_    # ln(base_pressure)

        latest_t = xs[-1][0]
        latest_pressure = float(np.exp(slope * latest_t + intercept))

        if slope <= 0:
            return {
                "status": "stable",
                "message": "Presiunea nu prezinta o tendinta de crestere; filtrul pare stabil.",
                "days_remaining": None,
                "current_pressure_bar": round(latest_pressure, 3),
                "degradation_rate_per_hour": round(slope * 3600, 6),
            }

        # rezolvam exp(slope * t + intercept) = clog_threshold => t
        t_threshold = (math.log(self.clog_threshold_bar) - intercept) / slope
        seconds_remaining = max(t_threshold - latest_t, 0)
        days_remaining = seconds_remaining / 86400

        r_squared = model.score(xs, log_ys)

        return {
            "status": "ok",
            "days_remaining": round(days_remaining, 2),
            "current_pressure_bar": round(latest_pressure, 3),
            "clog_threshold_bar": self.clog_threshold_bar,
            "degradation_rate_per_hour": round(slope * 3600, 6),
            "r_squared": round(float(r_squared), 4),
            "points_used": int(len(xs)),
        }
