"""
Aplicatie FastAPI - punctul central al backend-ului.

- La startup, porneste subscriber-ul MQTT (thread separat) care scrie
  fiecare citire de la senzorul virtual in InfluxDB.
- Expune endpoint-uri REST pentru:
    GET /health              -> verificare rapida ca serviciul e sus
    GET /latest               -> ultima citire primita prin MQTT
    GET /history?hours=24     -> istoricul citirilor din InfluxDB
    GET /predict               -> predictie ML: zile ramase pana la infundare
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

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
    print("[main] Backend pornit, subscriber MQTT activ.")
    yield
    subscriber.stop()
    db_writer.close()
    print("[main] Backend oprit.")


app = FastAPI(title="Water Filter Monitor API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/latest")
def get_latest():
    if not latest_reading:
        return {"status": "no_data", "message": "Nicio citire primita inca."}
    return latest_reading


@app.get("/history")
def get_history(hours: int = Query(24, ge=1, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    return {"count": len(readings), "readings": readings}


@app.get("/predict")
def predict(hours: int = Query(24, ge=1, le=24 * 30)):
    readings = db_writer.get_recent_readings(hours=hours)
    result = predictor.predict_days_remaining(readings)
    return result
