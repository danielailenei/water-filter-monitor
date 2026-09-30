"""
Ingest + alerting worker - runs as a single instance next to the API.

Subscribes to the sensor's MQTT topic, stores every reading in InfluxDB and
sends the 80/90/100% alerts. Kept out of the API (main.py) because the API is
scaled horizontally: with the subscriber inside it, every API replica would
store and alert on every reading, so alerts went out once per replica.

Run:  python worker.py   (same image as the API, different command)
"""

import signal
import sys

from alerting import AlertManager
from db_writer import DBWriter
from mqtt_subscriber import MqttSubscriber


def main():
    db_writer = DBWriter()
    subscriber = MqttSubscriber(db_writer, AlertManager(store=db_writer))

    def shutdown(signum, frame):
        # ECS sends SIGTERM on stop/deploy
        print("[worker] stopping.")
        subscriber.stop()
        db_writer.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print("[worker] up, subscribing to MQTT.")
    subscriber.run_forever()


if __name__ == "__main__":
    main()
