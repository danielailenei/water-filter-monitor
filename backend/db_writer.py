"""
Wrapper subtire peste InfluxDB Client, pentru scrierea citirilor de senzor
si citirea istoricului (folosit atat de endpoint-urile FastAPI cat si de
modelul ML pentru antrenare/predictie).
"""

import os
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "dev-super-secret-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "disertatie")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "water_filter")

MEASUREMENT = "filter_reading"


class DBWriter:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def write_reading(self, data: dict):
        point = (
            Point(MEASUREMENT)
            .field("pressure_drop_bar", float(data["pressure_drop_bar"]))
            .field("flow_rate_lmin", float(data["flow_rate_lmin"]))
            .field("turbidity_ntu", float(data["turbidity_ntu"]))
            .field("is_clogged", bool(data.get("is_clogged", False)))
            .time(datetime.now(timezone.utc), WritePrecision.NS)
        )
        self.write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

    def get_recent_readings(self, hours: int = 24):
        """Intoarce ultimele citiri (ca lista de dict-uri) din ultimele `hours` ore."""
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        tables = self.query_api.query(query, org=INFLUX_ORG)

        rows = []
        for table in tables:
            for record in table.records:
                rows.append({
                    "time": record.get_time(),
                    "pressure_drop_bar": record.values.get("pressure_drop_bar"),
                    "flow_rate_lmin": record.values.get("flow_rate_lmin"),
                    "turbidity_ntu": record.values.get("turbidity_ntu"),
                    "is_clogged": record.values.get("is_clogged"),
                })
        return rows

    def close(self):
        self.client.close()
