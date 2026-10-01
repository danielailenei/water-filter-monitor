"""Test de scalare a backend-ului sub stres CPU.

Spre deosebire de load-test.py (cereri HTTP -> backend -> InfluxDB), aici incarcam DOAR CPU-ul taskurilor
backend, prin ECS Exec, ca scalarea sa depinda numai de CPU-ul serviciului scalat:

  - la fiecare 15 s: citeste serviciul backend (desired/running) si taskurile; fiecare task backend nou
    primeste prin ECS Exec un proces care tine CPU-ul ocupat pana la sfarsitul fazei de stres
    (cu `nice 10`, ca aplicatia sa aiba prioritate -> /health continua sa raspunda);
  - in paralel, o sonda trimite GET /health de 2 ori pe secunda si noteaza orice raspuns != 200
    (verificam daca apar erori 5xx la scale out / scale in);
  - dupa faza de stres asteapta revenirea la 1 task (scale in ~15 min) sau limita de timp.

Rezultate in <out>: timeline.csv, events.log, summary.txt. Necesita AWS CLI, session-manager-plugin, profilul wfm.

    python scripts/cpu-stress.py https://<distributia>.cloudfront.net --stress-minutes 12 --out docs/capturi/8.3
"""

import argparse
import base64
import csv
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

CLUSTER, SERVICE, CONTAINER = "wfm-stage", "backend", "backend"
ENV = dict(os.environ, AWS_PROFILE=os.environ.get("AWS_PROFILE", "wfm"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

# Rulat in container: bucla ocupata pana la un moment absolut (epoch), cu prioritate scazuta
STRESS_CODE = """
import os, time
os.nice(10)
end = {end}
while time.time() < end:
    pass
print("stress done")
"""

lock = threading.Lock()
stop = threading.Event()


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def aws_json(*args):
    out = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True,
                         encoding="utf-8", env=ENV, check=True).stdout
    return json.loads(out)


def log(events, msg):
    line = f"{now()} {msg}"
    print(line, flush=True)
    with lock:
        events.write(line + "\n")
        events.flush()


def probe(url, events, counters):
    """GET /health de 2 ori pe secunda; orice raspuns != 200 e notat cu ora exacta."""
    while not stop.is_set():
        started = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:  # timeout, conexiune inchisa
            status = type(e).__name__
        with lock:
            counters["total"] += 1
            if status != 200:
                counters["errors"] += 1
        if status != 200:
            log(events, f"PROBE {status}")
        stop.wait(max(0.0, 0.5 - (time.monotonic() - started)))


def start_stress(task_arn, end_epoch):
    payload = base64.b64encode(STRESS_CODE.format(end=end_epoch).encode()).decode()
    command = f"python -c \"exec(__import__('base64').b64decode('{payload}'))\""
    return subprocess.Popen(
        ["aws", "ecs", "execute-command", "--cluster", CLUSTER, "--task", task_arn, "--container", CONTAINER,
         "--interactive", "--command", command],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=ENV)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("app_url")
    p.add_argument("--stress-minutes", type=float, default=12)
    p.add_argument("--max-minutes", type=float, default=40)
    p.add_argument("--out", default="docs/capturi/8.3")
    a = p.parse_args()

    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    stress_end = t0 + a.stress_minutes * 60
    deadline = t0 + a.max_minutes * 60

    events = open(os.path.join(a.out, "events.log"), "a", encoding="utf-8")
    timeline_f = open(os.path.join(a.out, "timeline.csv"), "a", newline="", encoding="utf-8")
    timeline = csv.writer(timeline_f)
    timeline.writerow(["utc", "desired", "running", "stressed_now", "probe_total", "probe_errors"])

    counters = {"total": 0, "errors": 0}
    threading.Thread(target=probe, args=(a.app_url.rstrip("/") + "/health", events, counters), daemon=True).start()

    log(events, f"START stres {a.stress_minutes} min (pana la "
                f"{datetime.fromtimestamp(stress_end, timezone.utc):%H:%M:%S} UTC), limita {a.max_minutes} min")
    procs = {}  # task ARN -> Popen
    max_tasks = 0
    try:
        while time.time() < deadline:
            svc = aws_json("ecs", "describe-services", "--cluster", CLUSTER, "--services", SERVICE)["services"][0]
            tasks = aws_json("ecs", "list-tasks", "--cluster", CLUSTER, "--service-name", SERVICE,
                             "--desired-status", "RUNNING")["taskArns"]
            max_tasks = max(max_tasks, svc["runningCount"])

            # ECS Exec esuat (ex. agentul inca porneste in taskul nou) -> reincercam la urmatorul pas
            for arn, proc in list(procs.items()):
                if proc.poll() not in (None, 0) and time.time() < stress_end - 30:
                    err = proc.stderr.read().decode(errors="replace").strip().splitlines()
                    log(events, f"EXEC esuat {arn[-8:]}: {err[-1] if err else proc.returncode} -> reincerc")
                    del procs[arn]

            if time.time() < stress_end - 30:
                for arn in tasks:
                    if arn not in procs:
                        procs[arn] = start_stress(arn, int(stress_end))
                        log(events, f"STRES pornit pe task {arn[-8:]}")
            stressed = sum(1 for arn in tasks if arn in procs and procs[arn].poll() is None)

            with lock:
                row = [now(), svc["desiredCount"], svc["runningCount"], stressed, counters["total"], counters["errors"]]
            timeline.writerow(row)
            timeline_f.flush()
            print(f"{row[0]} desired={row[1]} running={row[2]} stresate={row[3]} "
                  f"sonda={row[4]} erori={row[5]}", flush=True)

            # Gata: stresul s-a terminat de 2+ min si serviciul a revenit la un singur task
            if time.time() > stress_end + 120 and svc["desiredCount"] == 1 and svc["runningCount"] == 1 \
                    and max_tasks > 1:
                log(events, "REVENIT la 1 task -> sfarsit")
                break
            time.sleep(15)
    finally:
        stop.set()
        for proc in procs.values():
            if proc.poll() is None:
                proc.terminate()
        summary = (f"start {datetime.fromtimestamp(t0, timezone.utc):%Y-%m-%d %H:%M:%S} UTC, "
                   f"durata {(time.time() - t0) / 60:.1f} min, stres {a.stress_minutes} min, "
                   f"max taskuri {max_tasks}, sonda /health: {counters['total']} cereri, {counters['errors']} erori")
        log(events, "SUMAR " + summary)
        with open(os.path.join(a.out, "summary.txt"), "w", encoding="utf-8") as f:
            f.write(summary + "\n")


if __name__ == "__main__":
    main()
