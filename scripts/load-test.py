"""Generator de incarcare HTTP pentru testul de autoscaling al backend-ului.

Trimite cereri HTTP concurente catre o adresa si afiseaza la fiecare 10 s
numarul de cereri, erorile si latenta medie. Doar biblioteca standard.

Rulare:
    python scripts/load-test.py https://<distributia>.cloudfront.net/predict?hours=24 --minutes 10 --workers 30
"""

import argparse
import threading
import time
import urllib.request

lock = threading.Lock()
stats = {"ok": 0, "err": 0, "latency": 0.0}
stop = threading.Event()


def worker(url):
    while not stop.is_set():
        start = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                resp.read()
            ok = True
        except Exception:
            ok = False
        elapsed = time.monotonic() - start
        with lock:
            if ok:
                stats["ok"] += 1
                stats["latency"] += elapsed
            else:
                stats["err"] += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--minutes", type=float, default=10)
    parser.add_argument("--workers", type=int, default=30)
    args = parser.parse_args()

    for _ in range(args.workers):
        threading.Thread(target=worker, args=(args.url,), daemon=True).start()

    end = time.monotonic() + args.minutes * 60
    print(f"{args.workers} workeri, {args.minutes} min -> {args.url}", flush=True)
    while time.monotonic() < end:
        time.sleep(10)
        with lock:
            ok, err, lat = stats["ok"], stats["err"], stats["latency"]
            stats.update(ok=0, err=0, latency=0.0)
        avg = lat / ok if ok else 0
        print(f"{time.strftime('%H:%M:%S')}  ok={ok:5d}  err={err:4d}  "
              f"rps={ok / 10:6.1f}  latenta_medie={avg * 1000:7.0f} ms", flush=True)
    stop.set()


if __name__ == "__main__":
    main()
