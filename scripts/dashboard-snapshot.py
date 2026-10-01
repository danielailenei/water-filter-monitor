"""Salveaza ca PNG fiecare grafic din dashboard-ul CloudWatch `wfm-stage`, pe un interval dat.

Folosit pentru capturile testelor de scalare. Necesita AWS CLI si profilul `wfm`.

    python scripts/dashboard-snapshot.py 2026-09-30T08:15:00Z 2026-09-30T09:00:00Z docs/capturi/8.3
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

ENV = dict(os.environ, AWS_PROFILE=os.environ.get("AWS_PROFILE", "wfm"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def aws(*args):
    return subprocess.run(["aws", *args], capture_output=True, text=True, encoding="utf-8", env=ENV, check=True).stdout


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    start, end, out_dir = sys.argv[1:]
    os.makedirs(out_dir, exist_ok=True)

    body = json.loads(json.loads(aws("cloudwatch", "get-dashboard", "--dashboard-name", "wfm-stage",
                                     "--query", "DashboardBody", "--output", "json")))
    metric_widgets = [w["properties"] for w in body["widgets"] if w["type"] == "metric"]
    with tempfile.TemporaryDirectory() as tmp:
        for i, props in enumerate(metric_widgets, start=1):
            spec = os.path.join(tmp, "widget.json")
            # ensure_ascii: AWS CLI pe Windows citeste file:// in cp1252 -> diacriticele doar ca \uXXXX
            with open(spec, "w", encoding="utf-8") as f:
                json.dump(dict(props, start=start, end=end, width=900, height=380), f, ensure_ascii=True)
            png = aws("cloudwatch", "get-metric-widget-image", "--metric-widget", f"file://{spec}",
                      "--query", "MetricWidgetImage", "--output", "text")
            path = os.path.join(out_dir, f"{i:02d}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(png.strip()))
            print(path, "-", props["title"])


if __name__ == "__main__":
    main()
