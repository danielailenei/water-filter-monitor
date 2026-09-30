"""
Degradation model for a clogging water filter.

Physics: the filter sits in series with the rest of the plumbing, fed at the
(constant) mains supply pressure P_s. As particles build up, the filter's
hydraulic resistance R_f grows exponentially over time; the rest of the system
keeps a constant resistance R_sys. With x = R_f / R_sys:

    x(t)      = x0 * e^(k*t)                    exponential clogging
    pressure  = P_s * x / (1 + x)               drop across the filter
    flow      = P_s / (R_sys + R_f)             -> linear in the pressure drop

so the pressure drop starts at the new-filter value, grows almost
exponentially, and levels off smoothly at P_s (a fully blocked filter takes
the whole supply pressure); the flow falls from the new-filter value to zero.
Filtered-water turbidity rises with the clogging fraction towards the
turbidity of the raw water. Inverting x(t) gives the exact time to any
pressure, used as the reference for the backend's prediction.
"""

import math
import random


class FilterModel:
    def __init__(self, clogging_rate: float = 0.0008, base_pressure: float = 0.2,
                 base_flow: float = 15.0, base_turbidity: float = 0.5,
                 clog_threshold_bar: float = 1.5,
                 supply_pressure_bar: float = 4.0, max_turbidity_ntu: float = 10.0):
        self.clogging_rate = clogging_rate            # k, per simulated hour
        self.base_pressure = base_pressure            # pressure drop of a new filter (bar)
        self.base_flow = base_flow                    # flow of a new filter (L/min)
        self.base_turbidity = base_turbidity          # filtered turbidity, new filter (NTU)
        self.clog_threshold_bar = clog_threshold_bar  # pressure above which the filter is "clogged"
        self.supply_pressure = supply_pressure_bar    # mains pressure: the ceiling of the drop
        self.max_turbidity_ntu = max_turbidity_ntu    # raw-water turbidity: the ceiling
        # resistance ratio of a new filter, from its pressure drop
        self.x0 = base_pressure / (supply_pressure_bar - base_pressure)

    # ---- noiseless physics ----

    def _ratio(self, elapsed_hours: float) -> float:
        return self.x0 * math.exp(self.clogging_rate * elapsed_hours)

    def true_pressure(self, elapsed_hours: float) -> float:
        x = self._ratio(elapsed_hours)
        return self.supply_pressure * x / (1 + x)

    def clogging_fraction(self, pressure_drop: float) -> float:
        """0 for a new filter, 1 for a fully blocked one."""
        frac = (pressure_drop - self.base_pressure) / (self.supply_pressure - self.base_pressure)
        return min(max(frac, 0.0), 1.0)

    # ---- sensor readings (with measurement noise) ----

    def pressure_drop(self, elapsed_hours: float) -> float:
        """Pressure drop (bar) after `elapsed_hours` of (accelerated) operation."""
        p = self.true_pressure(elapsed_hours) + random.uniform(-0.02, 0.02)
        return round(min(max(p, 0.0), self.supply_pressure), 3)

    def flow_rate(self, pressure_drop: float) -> float:
        """Flow (L/min): the pressure left to push water through falls as the filter blocks."""
        flow = self.base_flow * (1 - self.clogging_fraction(pressure_drop))
        return round(max(flow + random.uniform(-0.15, 0.15), 0.0), 2)

    def turbidity(self, pressure_drop: float) -> float:
        """Turbidity (NTU): retention drops as the filter clogs, towards the raw water's."""
        value = self.base_turbidity + (self.max_turbidity_ntu - self.base_turbidity) \
            * self.clogging_fraction(pressure_drop)
        value += random.uniform(-0.05, 0.05)
        return round(min(max(value, 0.0), self.max_turbidity_ntu), 2)

    def is_clogged(self, pressure_drop: float) -> bool:
        return pressure_drop >= self.clog_threshold_bar

    # ---- reference prediction ----

    def seconds_to_threshold(self, elapsed_hours: float, time_acceleration: float) -> float:
        """Exact real-time seconds until the (noiseless) pressure reaches the clog
        threshold - the ground truth the backend's regression is compared with."""
        x_thr = self.clog_threshold_bar / (self.supply_pressure - self.clog_threshold_bar)
        hours_at_threshold = math.log(x_thr / self.x0) / self.clogging_rate
        sim_hours_left = max(hours_at_threshold - elapsed_hours, 0.0)
        return sim_hours_left * 3600 / (time_acceleration or 1)

    def estimate_days_remaining(self, elapsed_hours: float, time_acceleration: float) -> float:
        # 6 decimals (~0.1 s): 2 decimals would round to 0.01 days = 14.4 minutes
        return round(self.seconds_to_threshold(elapsed_hours, time_acceleration) / 86400, 6)
