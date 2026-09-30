"""
FastAPI app - the API + dashboard. Stateless: every value comes from InfluxDB,
so it can run as several replicas behind the load balancer. Readings are
stored (and alerts sent) by the single worker, see worker.py.

Exposes:
    GET /health              - liveness check
    GET /latest              - most recent reading
    GET /history?hours=24    - reading history from InfluxDB
    GET /predict?hours=24    - predicted time until the filter clogs (current cycle)
    GET /alerts?hours=24     - recent alert events (sent / filter reset)
    GET /config              - public links for the dashboard (Grafana URL)
"""

import os

from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles

from db_writer import DBWriter
from ml_model import FilterPredictor

# localhost:3000 with docker compose, /grafana/ behind CloudFront on AWS
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000").rstrip("/")

db_writer = DBWriter()
predictor = FilterPredictor()

app = FastAPI(title="Water Filter Monitor API")


@app.middleware("http")
async def no_cache(request: Request, call_next):
    # Live data and a dashboard that changes with every deploy: the browser must
    # revalidate each time, otherwise an old app.js keeps running after a deploy.
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/latest")
def get_latest():
    reading = db_writer.get_latest_reading()
    if reading is None:
        return {"status": "no_data", "message": "No reading in the last 10 minutes."}
    return reading


@app.get("/history")
def get_history(hours: float = Query(24, ge=0.05, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    return {"count": len(readings), "readings": readings}


@app.get("/predict")
def predict(hours: int = Query(24, ge=1, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    return predictor.predict_days_remaining(readings)


@app.get("/alerts")
def get_alerts(hours: int = Query(24, ge=1, le=24 * 30)):
    return {"events": db_writer.get_alert_events(hours=hours)}


@app.get("/config")
def config():
    # The dashboard asks for the Grafana address, which differs per environment
    return {"grafana_url": GRAFANA_URL}


# Static dashboard - served on the same origin as the API, so the frontend needs
# no CORS and there is only one service to expose. Mounted last so it never
# shadows the API routes above; the directory is relative to the backend working
# dir (WORKDIR /app in the Dockerfile).
app.mount("/", StaticFiles(directory="static", html=True), name="ui")
