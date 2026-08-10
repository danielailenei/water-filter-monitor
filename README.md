# Water Filter Monitor

Sistem IoT simulat pentru monitorizarea și predicția înfundării unui filtru
de apă — senzor virtual → MQTT → backend FastAPI → InfluxDB → Grafana,
cu simulare opțională a impactului rețelei (ns-3/5G, rulat separat în WSL2).

Vezi [docs/arhitectura.md](docs/arhitectura.md) pentru detalii de arhitectură
și argumentarea alegerilor tehnice.

## Pornire rapidă

### 1. Pornește infrastructura (Mosquitto, InfluxDB, backend, Grafana)

```bash
docker compose up --build
```

Servicii disponibile:

- Backend API: http://localhost:8000 (`/health`, `/latest`, `/history`, `/predict`)
- InfluxDB UI: http://localhost:8086 (user: `admin`, parola: `admin12345`)
- Grafana: http://localhost:3000 (user: `admin`, parola: `admin`)

### 2. Pornește senzorul virtual (separat, direct cu Python)

```bash
cd sensor
pip install -r requirements.txt
python virtual_sensor.py
```

Senzorul se conectează la Mosquitto pe `localhost:1883` și publică citiri
la fiecare 5 secunde (interval configurabil în `sensor/config.yaml`).

### 3. Verifică

```bash
curl http://localhost:8000/latest
curl http://localhost:8000/predict
```

În Grafana (http://localhost:3000), dashboard-ul "Water Filter Monitor" e
provizionat automat și ar trebui să înceapă să arate date live după câteva
citiri.

## Structură

```
water-filter-monitor/
├── docker-compose.yml
├── .env
├── sensor/            # senzor virtual (Python, MQTT publisher)
├── backend/            # FastAPI: MQTT subscriber, InfluxDB writer, predictie ML
├── network_sim/         # rezultate latenta din ns-3 (rulat separat, WSL2)
├── grafana/provisioning/ # datasource + dashboard provizionate automat
└── docs/                # documentatie de arhitectura
```
