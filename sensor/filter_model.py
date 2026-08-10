"""
Model matematic simplificat de degradare (colmatare) a unui filtru de apa.

Ideea fizica:
- Pe masura ce filtrul retine impuritati, porii se colmateaza treptat.
- Asta duce la o crestere (aproximativ exponentiala) a caderii de presiune
  (pressure drop) intre intrarea si iesirea filtrului.
- Debitul (flow rate) scade invers proportional cu presiunea diferentiala.
- Turbiditatea apei filtrate creste usor pe masura ce filtrul isi pierde
  eficienta de retinere.

Parametrii sunt ajustabili din config.yaml, ca sa poti simula filtre cu
viteze de colmatare diferite (scenarii pentru comparatie in disertatie).
"""

import math
import random


class FilterModel:
    def __init__(self, clogging_rate: float = 0.0008, base_pressure: float = 0.2,
                 base_flow: float = 15.0, base_turbidity: float = 0.5,
                 clog_threshold_bar: float = 1.5):
        """
        clogging_rate: cat de repede se degradeaza filtrul (constanta din exponentiala)
        base_pressure: cadere de presiune a unui filtru nou, in bar
        base_flow: debit maxim al unui filtru nou, in L/min
        base_turbidity: turbiditate de baza a apei filtrate, in NTU
        clog_threshold_bar: pragul de presiune peste care filtrul e considerat "infundat"
        """
        self.clogging_rate = clogging_rate
        self.base_pressure = base_pressure
        self.base_flow = base_flow
        self.base_turbidity = base_turbidity
        self.clog_threshold_bar = clog_threshold_bar

    def pressure_drop(self, elapsed_hours: float) -> float:
        """Cadere de presiune (bar) in functie de orele de functionare (accelerate)."""
        degradation = self.base_pressure * math.exp(self.clogging_rate * elapsed_hours)
        noise = random.uniform(-0.02, 0.02)
        return round(degradation + noise, 3)

    def flow_rate(self, pressure_drop: float) -> float:
        """Debit (L/min) - scade pe masura ce presiunea diferentiala creste."""
        flow = self.base_flow / (1 + pressure_drop)
        noise = random.uniform(-0.3, 0.3)
        return round(max(flow + noise, 0), 2)

    def turbidity(self, pressure_drop: float) -> float:
        """Turbiditate (NTU) - creste usor odata cu degradarea filtrului."""
        value = self.base_turbidity + pressure_drop * 2 + random.uniform(-0.1, 0.1)
        return round(max(value, 0), 2)

    def is_clogged(self, pressure_drop: float) -> bool:
        return pressure_drop >= self.clog_threshold_bar

    def estimate_days_remaining(self, elapsed_hours: float, time_acceleration: float) -> float:
        """
        Estimare analitica (folosita ca referinta / ground truth) a orelor ramase
        pana cand presiunea atinge pragul de infundare, pornind din formula
        exponentiala inversata. Utila pentru a compara predictia modelului ML
        din backend cu valoarea "reala" simulata.
        """
        current_pressure = self.base_pressure * math.exp(self.clogging_rate * elapsed_hours)
        if current_pressure <= 0:
            return float("inf")
        hours_at_threshold = math.log(self.clog_threshold_bar / self.base_pressure) / self.clogging_rate
        hours_remaining_sim = max(hours_at_threshold - elapsed_hours, 0)
        # convertim din ore "de simulare accelerata" in zile reale de utilizare
        real_hours_remaining = hours_remaining_sim / time_acceleration if time_acceleration else hours_remaining_sim
        return round(real_hours_remaining / 24, 2)
