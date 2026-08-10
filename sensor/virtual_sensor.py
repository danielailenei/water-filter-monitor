"""
Senzor virtual pentru monitorizarea unui filtru de apa.

Simuleaza presiunea diferentiala, debitul si turbiditatea folosind
FilterModel (vezi filter_model.py), si publica citirile periodic pe MQTT.

Optional, poate citi din network_sim/latency_output.csv latentele obtinute
dintr-o simulare ns-3/Simu5G si le aplica ca delay inainte de fiecare
publish(), pentru a demonstra impactul retelei asupra timpului de livrare.

Ruleaza direct cu Python (nu are nevoie de Docker), cat timp Mosquitto
este pornit (docker compose up mosquitto) si asculta pe localhost:1883.
"""

import csv
import itertools
import os
import time
import json

import yaml
import paho.mqtt.client as mqtt

from filter_model import FilterModel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_latency_cycle(latency_file: str):
    """
    Citeste network_sim/latency_output.csv (coloana 'latency_ms') si intoarce
    un iterator infinit peste valorile de latenta, in secunde.
    Daca fisierul nu exista inca (ns-3 nu a fost rulat), intoarce None.
    """
    path = os.path.join(os.path.dirname(__file__), latency_file)
    if not os.path.exists(path):
        print(f"[!] Fisier de latenta negasit ({path}); continui fara delay de retea.")
        return None

    values = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                values.append(float(row["latency_ms"]) / 1000.0)
            except (KeyError, ValueError):
                continue

    if not values:
        print(f"[!] Fisierul de latenta {path} nu are date valide; continui fara delay.")
        return None

    return itertools.cycle(values)


def main():
    config = load_config()

    mqtt_cfg = config["mqtt"]
    sim_cfg = config["simulation"]
    net_cfg = config.get("network", {})

    model = FilterModel(
        clogging_rate=sim_cfg["clogging_rate"],
        base_pressure=sim_cfg["base_pressure_bar"],
        base_flow=sim_cfg["base_flow_lmin"],
        base_turbidity=sim_cfg["base_turbidity_ntu"],
        clog_threshold_bar=sim_cfg["clog_threshold_bar"],
    )

    time_acceleration = sim_cfg["time_acceleration"]
    publish_interval = sim_cfg["publish_interval_seconds"]

    latency_cycle = None
    if net_cfg.get("use_latency_file"):
        latency_cycle = load_latency_cycle(net_cfg["latency_file"])

    client = mqtt.Client()
    client.connect(mqtt_cfg["broker"], mqtt_cfg["port"], 60)
    client.loop_start()

    print(f"[*] Senzor virtual pornit. Public pe topicul '{mqtt_cfg['topic']}' "
          f"la fiecare {publish_interval}s (timp accelerat x{time_acceleration}).")

    start_time = time.time()

    try:
        while True:
            elapsed_hours = (time.time() - start_time) / 3600 * time_acceleration
            pressure_drop = model.pressure_drop(elapsed_hours)
            flow = model.flow_rate(pressure_drop)
            turbidity = model.turbidity(pressure_drop)
            clogged = model.is_clogged(pressure_drop)
            days_remaining_sim = model.estimate_days_remaining(elapsed_hours, time_acceleration)

            payload = {
                "timestamp": time.time(),
                "pressure_drop_bar": pressure_drop,
                "flow_rate_lmin": flow,
                "turbidity_ntu": turbidity,
                "is_clogged": clogged,
                "days_remaining_model": days_remaining_sim,
            }

            if latency_cycle is not None:
                delay = next(latency_cycle)
                time.sleep(delay)

            client.publish(mqtt_cfg["topic"], json.dumps(payload))
            print(f"Trimis: {payload}")

            time.sleep(publish_interval)
    except KeyboardInterrupt:
        print("\n[*] Oprire senzor virtual.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
