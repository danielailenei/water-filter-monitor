FROM python:3.11-slim

# Unbuffered stdout so print() from the alerting retries shows up in
# `docker compose logs` in real time, not all at once on flush.
ENV PYTHONUNBUFFERED=1

# Security updates from Debian at build time (the ECR scan flagged openssl in
# the base image), then an unprivileged user - the app writes nothing to disk.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Copy requirements first so `pip install` is cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER app
EXPOSE 8000

# --no-server-header: don't advertise the web server in every response
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
