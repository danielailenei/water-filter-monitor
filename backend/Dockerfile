FROM python:3.11-slim

# Unbuffered stdout so print() from the alerting retries shows up in
# `docker compose logs` in real time, not all at once on flush.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first so `pip install` is cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
