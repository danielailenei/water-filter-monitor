"""
FastAPI app - the backend entry point.

On startup it launches the MQTT subscriber (separate thread) that writes every
sensor reading to InfluxDB. Exposes:
    GET /health              - liveness check
    GET /latest              - last reading received over MQTT
    GET /history?hours=24    - reading history from InfluxDB
    GET /predict?hours=24    - predicted days until the filter clogs
    GET /config              - public links for the dashboard (Grafana URL)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles

from alerting import GRAFANA_URL
from db_writer import DBWriter
from mqtt_subscriber import MqttSubscriber
from ml_model import FilterPredictor

db_writer = DBWriter()
predictor = FilterPredictor()
latest_reading: dict = {}
subscriber = MqttSubscriber(db_writer, latest_reading)


@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber.start()
    print("[main] backend up, MQTT subscriber running.")
    yield
    subscriber.stop()
    db_writer.close()
    print("[main] backend stopped.")


app = FastAPI(title="Water Filter Monitor API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/latest")
def get_latest():
    if not latest_reading:
        return {"status": "no_data", "message": "No reading received yet."}
    return latest_reading


@app.get("/history")
def get_history(hours: float = Query(24, ge=0.05, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    return {"count": len(readings), "readings": readings}


@app.get("/predict")
def predict(hours: int = Query(24, ge=1, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    return predictor.predict_days_remaining(readings)


@app.get("/config")
def config():
    # The Grafana address differs per environment (localhost:3000 locally,
    # /grafana/ behind CloudFront on AWS), so the dashboard asks for it.
    return {"grafana_url": GRAFANA_URL}


# Static dashboard - served on the same origin as the API, so the frontend needs
# no CORS and there is only one service to expose. Mounted last so it never
# shadows the API routes above; the directory is relative to the backend working
# dir (WORKDIR /app in the Dockerfile).
app.mount("/", StaticFiles(directory="static", html=True), name="ui")
