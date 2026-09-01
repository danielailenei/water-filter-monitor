# Mirrors backend/Dockerfile. The sensor is plain Python + paho-mqtt; it runs
# here as a stack service so a server deploy needs no separate process, and
# still runs the same via `python virtual_sensor.py` for local iteration.
FROM python:3.11-slim

# Unbuffered stdout so the per-reading print() lines show up in
# `docker compose logs` in real time, not all at once on flush.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first so `pip install` is cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "virtual_sensor.py"]
