"""Genereaza diagrama de arhitectura pentru lucrarea de disertatie (stil academic, alb-negru)."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(10, 4.9), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(1.3, 6.2)
ax.axis("off")
fig.patch.set_facecolor("white")

BOX_EDGE = "#222222"
BOX_FILL = "#f4f4f2"
BOX_FILL_DASH = "#ffffff"
TEXT_COLOR = "#111111"
ARROW_COLOR = "#333333"


def box(x, y, w, h, title, subtitle=None, dashed=False, fontsize=10.5):
    style = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4,
        edgecolor=BOX_EDGE,
        facecolor=BOX_FILL_DASH if dashed else BOX_FILL,
        linestyle="dashed" if dashed else "solid",
    )
    ax.add_patch(style)
    cy = y + h / 2 + (0.14 if subtitle else 0)
    ax.text(x + w / 2, cy, title, ha="center", va="center",
             fontsize=fontsize, fontweight="bold", color=TEXT_COLOR)
    if subtitle:
        ax.text(x + w / 2, y + h / 2 - 0.22, subtitle, ha="center", va="center",
                 fontsize=8.3, color="#444444")
    return (x, y, w, h)


def arrow(b1, b2, side1="right", side2="left", label=None, dashed=False, curve=0.0, label_dy=0.14):
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    pts = {
        "right": (x1 + w1, y1 + h1 / 2), "left": (x1, y1 + h1 / 2),
        "top": (x1 + w1 / 2, y1 + h1), "bottom": (x1 + w1 / 2, y1),
    }
    pts2 = {
        "right": (x2 + w2, y2 + h2 / 2), "left": (x2, y2 + h2 / 2),
        "top": (x2 + w2 / 2, y2 + h2), "bottom": (x2 + w2 / 2, y2),
    }
    p1 = pts[side1]
    p2 = pts2[side2]
    a = FancyArrowPatch(
        p1, p2,
        arrowstyle="-|>", mutation_scale=13, linewidth=1.3,
        color=ARROW_COLOR, connectionstyle=f"arc3,rad={curve}",
        linestyle="dashed" if dashed else "solid",
        shrinkA=2, shrinkB=2,
    )
    ax.add_patch(a)
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + label_dy
        ax.text(mx, my, label, ha="center", va="center", fontsize=8, color="#222222",
                 path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])


# --- Noduri ---
b_sensor = box(0.3, 3.9, 1.7, 1.0, "Senzor virtual", "Python, local")
b_mqtt = box(2.5, 3.9, 1.7, 1.0, "Mosquitto", "broker MQTT · :1883")
b_backend = box(4.7, 3.55, 2.15, 1.7, "Backend FastAPI", ":8000\nmqtt_subscriber\ndb_writer · ml_model")
b_influx = box(7.35, 3.9, 1.7, 1.0, "InfluxDB", ":8086")
b_grafana = box(7.35, 1.9, 1.7, 1.0, "Grafana", ":3000")
b_client = box(4.7, 1.55, 2.15, 1.0, "Client REST", "browser / curl")
b_ns3 = box(0.3, 1.55, 1.9, 1.15, "ns-3 / WSL2", "simulare retea\n(optional)", dashed=True, fontsize=9.5)

# --- Legaturi ---
arrow(b_sensor, b_mqtt, "right", "left", "publish JSON")
arrow(b_mqtt, b_backend, "right", "left", "subscribe")
arrow(b_backend, b_influx, "right", "left", "scrie puncte")
arrow(b_influx, b_grafana, "bottom", "top", "Flux query")
arrow(b_backend, b_client, "bottom", "top", "/latest /history\n/predict", label_dy=0.0)
arrow(b_ns3, b_sensor, "top", "bottom", "latency_output.csv\n(delay simulat)", dashed=True, curve=-0.15)

ax.text(5, 5.85, "Arhitectura sistemului Water Filter Monitor", ha="center", va="center",
         fontsize=13.5, fontweight="bold", color=TEXT_COLOR)

fig.tight_layout()
fig.savefig("architecture_diagram.png", facecolor="white", bbox_inches="tight")
print("OK")
