"""
Thin wrapper over the InfluxDB client: writes sensor readings and alert events,
and reads them back (history and latest reading for the API, alert state for
the worker).
"""

import os
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "changeme")
INFLUX_ORG = os.getenv("INFLUX_ORG", "disertatie")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "water_filter")

MEASUREMENT = "filter_reading"
ALERT_MEASUREMENT = "alert_event"


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
        # The sensor's own estimate, shown next to the ML prediction on the dashboard
        if data.get("days_remaining_model") is not None:
            point.field("days_remaining_model", float(data["days_remaining_model"]))
        self.write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

    def _query_readings(self, flux_range: str, tail: str = "") -> list[dict]:
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: {flux_range})
          |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
          {tail}
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        rows = []
        for table in self.query_api.query(query, org=INFLUX_ORG):
            for record in table.records:
                rows.append({
                    "time": record.get_time(),
                    "pressure_drop_bar": record.values.get("pressure_drop_bar"),
                    "flow_rate_lmin": record.values.get("flow_rate_lmin"),
                    "turbidity_ntu": record.values.get("turbidity_ntu"),
                    "is_clogged": record.values.get("is_clogged"),
                    "days_remaining_model": record.values.get("days_remaining_model"),
                })
        return rows

    def get_recent_readings(self, hours: float = 24) -> list[dict]:
        """Return readings from the last `hours` hours, oldest first.

        `hours` may be fractional (the dashboard's 15-minute range passes 0.25);
        the Flux range is built in whole minutes since Flux has no fractional
        duration literal.
        """
        minutes = max(1, round(hours * 60))
        return self._query_readings(f"-{minutes}m")

    def get_latest_reading(self) -> dict | None:
        """The most recent reading (last 10 minutes), or None if the sensor is silent."""
        rows = self._query_readings("-10m", tail="|> last()")
        return rows[-1] if rows else None

    # ---- alert state, shared across restarts of the alerting worker ----

    def write_alert_event(self, kind: str, threshold: int = 0):
        """kind = "sent" (threshold notified) or "reset" (new filter cycle)."""
        point = (
            Point(ALERT_MEASUREMENT)
            .tag("kind", kind)
            .field("threshold", int(threshold))
            .time(datetime.now(timezone.utc), WritePrecision.NS)
        )
        self.write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

    def get_fired_thresholds(self, hours: int = 72) -> set[int]:
        """Thresholds already notified since the last reset (replays the events in order)."""
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r._measurement == "{ALERT_MEASUREMENT}" and r._field == "threshold")
          |> group()
          |> sort(columns: ["_time"])
        '''
        fired: set[int] = set()
        for table in self.query_api.query(query, org=INFLUX_ORG):
            for record in table.records:
                if record.values.get("kind") == "reset":
                    fired.clear()
                else:
                    fired.add(int(record.get_value()))
        return fired

    def get_alert_events(self, hours: int = 24, limit: int = 20) -> list[dict]:
        """Recent alert events (sent / reset), newest first - shown on the dashboard."""
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r._measurement == "{ALERT_MEASUREMENT}" and r._field == "threshold")
          |> group()
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
        '''
        events = []
        for table in self.query_api.query(query, org=INFLUX_ORG):
            for record in table.records:
                events.append({
                    "time": record.get_time(),
                    "kind": record.values.get("kind"),
                    "threshold": int(record.get_value()),
                })
        return events

    def close(self):
        self.client.close()
