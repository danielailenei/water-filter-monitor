"""
MQTT subscriber: listens on the sensor topic, writes each reading to InfluxDB
and checks the alert thresholds. Runs on its own paho loop thread, started from
main.py on app startup.
"""

import json
import os

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
        self.latest_reading_ref = latest_reading_ref  # shared with main.py
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[mqtt] connected (rc={rc}), subscribing to '{MQTT_TOPIC}'")
        client.subscribe(MQTT_TOPIC)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[mqtt] invalid message, ignored: {e}")
            return

        try:
            self.db_writer.write_reading(data)
            self.latest_reading_ref.update(data)
        except Exception as e:
            print(f"[mqtt] InfluxDB write failed: {e}")
            return

        try:
            pressure = float(data.get("pressure_drop_bar", 0))
            alert_manager.check_and_notify(pressure, CLOG_THRESHOLD_BAR)
        except Exception as e:
            print(f"[mqtt] alert check failed: {e}")

    def start(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
