"""
Subscriber MQTT care asculta pe topicul senzorului virtual si scrie fiecare
citire in InfluxDB. Ruleaza pe firul lui de executie propriu (loop_start),
pornit din main.py la startup-ul aplicatiei FastAPI.
"""

import json
import os
import threading

import paho.mqtt.client as mqtt

from db_writer import DBWriter
from alerting import alert_manager

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/water/filter")
CLOG_THRESHOLD_BAR = float(os.getenv("CLOG_THRESHOLD_BAR", "1.5"))


class MqttSubscriber:
    def __init__(self, db_writer: DBWriter, latest_reading_ref: dict):
        self.db_writer = db_writer
        self.latest_reading_ref = latest_reading_ref  # dict mutabil, partajat cu main.py
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._lock = threading.Lock()

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[mqtt] Conectat la broker (rc={rc}), subscriu la '{MQTT_TOPIC}'")
        client.subscribe(MQTT_TOPIC)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[mqtt] Mesaj invalid, ignorat: {e}")
            return

        try:
            self.db_writer.write_reading(data)
            with self._lock:
                self.latest_reading_ref.update(data)
            print(f"[mqtt] Citire scrisa in InfluxDB: {data}")
        except Exception as e:
            print(f"[mqtt] Eroare la scrierea in InfluxDB: {e}")
            return

        try:
            pressure = float(data.get("pressure_drop_bar", 0))
            alert_manager.check_and_notify(pressure, CLOG_THRESHOLD_BAR)
        except Exception as e:
            print(f"[mqtt] Eroare la verificarea alertelor: {e}")

    def start(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
