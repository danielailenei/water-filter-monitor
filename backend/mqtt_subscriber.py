"""
MQTT subscriber: listens on the sensor topic, writes each reading to InfluxDB
and checks the alert thresholds. Runs in the alerting worker (worker.py) - a
single instance, so every reading is stored and alerted on exactly once.
"""

import json
import os

import paho.mqtt.client as mqtt

from alerting import AlertManager
from db_writer import DBWriter

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/water/filter")
CLOG_THRESHOLD_BAR = float(os.getenv("CLOG_THRESHOLD_BAR", "1.5"))


class MqttSubscriber:
    def __init__(self, db_writer: DBWriter, alert_manager: AlertManager):
        self.db_writer = db_writer
        self.alert_manager = alert_manager
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
        except Exception as e:
            print(f"[mqtt] InfluxDB write failed: {e}")
            return

        try:
            pressure = float(data.get("pressure_drop_bar", 0))
            self.alert_manager.check_and_notify(pressure, CLOG_THRESHOLD_BAR, reading=data)
        except Exception as e:
            print(f"[mqtt] alert check failed: {e}")

    def run_forever(self):
        # paho reconnects on its own if the broker restarts
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_forever(retry_first_connection=True)

    def stop(self):
        self.client.disconnect()
