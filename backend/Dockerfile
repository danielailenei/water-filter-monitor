FROM python:3.11-slim

# Fara asta, Python bufferizeaza stdout cand nu scrie intr-un terminal (cazul
# unui container Docker), asa ca toate mesajele print() dintr-un lot de
# alerte (chiar si cele separate prin time.sleep(20) in alerting.py) apar
# deodata la flush, cu acelasi timestamp in "docker compose logs" - facand
# imposibila verificarea reala a esalonarii alertelor din loguri.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
