"""
Degradation model for a clogging water filter.

As the filter traps particles its pores clog up, so the pressure drop across
it rises roughly exponentially over time. Flow rate falls as pressure rises,
and filtered-water turbidity creeps up as retention efficiency drops. All
parameters come from config.yaml so different clogging rates can be simulated.
"""

import math
import random


class FilterModel:
    def __init__(self, clogging_rate: float = 0.0008, base_pressure: float = 0.2,
                 base_flow: float = 15.0, base_turbidity: float = 0.5,
                 clog_threshold_bar: float = 1.5,
                 max_pressure_bar: float = 4.0, max_turbidity_ntu: float = 10.0):
        self.clogging_rate = clogging_rate          # exponential growth constant
        self.base_pressure = base_pressure          # pressure drop of a new filter (bar)
        self.base_flow = base_flow                  # max flow of a new filter (L/min)
        self.base_turbidity = base_turbidity        # baseline filtered-water turbidity (NTU)
        self.clog_threshold_bar = clog_threshold_bar  # pressure above which the filter is "clogged"
        # Physical ceilings - a real filter does not diverge to infinity. The
        # differential pressure cannot exceed the mains supply pressure, and a
        # failed filter's output turbidity approaches that of the source water.
        self.max_pressure_bar = max_pressure_bar
        self.max_turbidity_ntu = max_turbidity_ntu

    def pressure_drop(self, elapsed_hours: float) -> float:
        """Pressure drop (bar) as a function of (accelerated) operating hours."""
        degradation = self.base_pressure * math.exp(self.clogging_rate * elapsed_hours)
        noise = random.uniform(-0.02, 0.02)
        return round(min(degradation + noise, self.max_pressure_bar), 3)

    def flow_rate(self, pressure_drop: float) -> float:
        """Flow rate (L/min) - drops as the differential pressure rises."""
        flow = self.base_flow / (1 + pressure_drop)
        noise = random.uniform(-0.3, 0.3)
        return round(max(flow + noise, 0), 2)

    def turbidity(self, pressure_drop: float) -> float:
        """Turbidity (NTU) - rises slowly as the filter degrades."""
        value = self.base_turbidity + pressure_drop * 2 + random.uniform(-0.1, 0.1)
        return round(min(max(value, 0), self.max_turbidity_ntu), 2)

    def is_clogged(self, pressure_drop: float) -> bool:
        return pressure_drop >= self.clog_threshold_bar

    def estimate_days_remaining(self, elapsed_hours: float, time_acceleration: float) -> float:
        """
        Analytic ground truth for days left until the pressure reaches the clog
        threshold, from the inverted exponential. Used as a reference to compare
        against the backend's regression-based prediction.
        """
        if self.base_pressure <= 0:
            return float("inf")
        hours_at_threshold = math.log(self.clog_threshold_bar / self.base_pressure) / self.clogging_rate
        sim_hours_remaining = max(hours_at_threshold - elapsed_hours, 0)
        real_hours_remaining = sim_hours_remaining / time_acceleration if time_acceleration else sim_hours_remaining
        return round(real_hours_remaining / 24, 2)
