"""
Virtual water-filter sensor: computes pressure, flow and turbidity from
FilterModel and publishes a JSON reading over MQTT every few seconds.

Runs with plain Python (no Docker) as long as Mosquitto is up on
localhost:1883 (docker compose up mosquitto).
"""

import json
import os
import time

import yaml
import paho.mqtt.client as mqtt

from filter_model import FilterModel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    mqtt_cfg = config["mqtt"]
    sim_cfg = config["simulation"]

    model = FilterModel(
        clogging_rate=sim_cfg["clogging_rate"],
        base_pressure=sim_cfg["base_pressure_bar"],
        base_flow=sim_cfg["base_flow_lmin"],
        base_turbidity=sim_cfg["base_turbidity_ntu"],
        clog_threshold_bar=sim_cfg["clog_threshold_bar"],
    )
    time_acceleration = sim_cfg["time_acceleration"]
    publish_interval = sim_cfg["publish_interval_seconds"]

    client = mqtt.Client()
    client.connect(mqtt_cfg["broker"], mqtt_cfg["port"], 60)
    client.loop_start()
    print(f"[sensor] Publishing to '{mqtt_cfg['topic']}' every {publish_interval}s "
          f"(time x{time_acceleration}).")

    start_time = time.time()
    try:
        while True:
            elapsed_hours = (time.time() - start_time) / 3600 * time_acceleration
            pressure_drop = model.pressure_drop(elapsed_hours)

            payload = {
                "timestamp": time.time(),
                "pressure_drop_bar": pressure_drop,
                "flow_rate_lmin": model.flow_rate(pressure_drop),
                "turbidity_ntu": model.turbidity(pressure_drop),
                "is_clogged": model.is_clogged(pressure_drop),
                "days_remaining_model": model.estimate_days_remaining(elapsed_hours, time_acceleration),
            }

            client.publish(mqtt_cfg["topic"], json.dumps(payload))
            print(f"[sensor] sent: {payload}")
            time.sleep(publish_interval)
    except KeyboardInterrupt:
        print("\n[sensor] stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
