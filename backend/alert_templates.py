"""
What the alerts look like: a colour-coded HTML email (with a plain-text
fallback) and an ntfy push. Kept apart from alerting.py, which decides *when*
to notify; this module only decides *how the message reads*.
"""

import html
import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo(os.getenv("ALERT_TIMEZONE", "Europe/Bucharest"))
except Exception:  # no tz database in the image -> UTC
    LOCAL_TZ = timezone.utc

# One entry per threshold: colours, wording, push priority and icon (ntfy tag)
LEVELS = {
    80: {
        "color": "#d97706", "tint": "#fef3c7",
        "headline": "Filtrul a ajuns la 80%",
        "subject": "Filtru la 80% – planifică înlocuirea",
        "advice": "Filtrul se colmatează vizibil. Planifică înlocuirea în perioada următoare.",
        "priority": 3, "tag": "warning",
    },
    90: {
        "color": "#ea580c", "tint": "#ffedd5",
        "headline": "Filtrul a ajuns la 90%",
        "subject": "Filtru la 90% – pregătește un filtru nou",
        "advice": "Filtrul este aproape înfundat. Pregătește un filtru de schimb.",
        "priority": 4, "tag": "orange_circle",
    },
    100: {
        "color": "#dc2626", "tint": "#fee2e2",
        "headline": "Filtrul este înfundat",
        "subject": "Filtru ÎNFUNDAT – înlocuiește-l",
        "advice": "Presiunea a depășit pragul de înfundare. Înlocuiește filtrul cât mai curând.",
        "priority": 5, "tag": "rotating_light",
    },
}


def _duration(seconds: float) -> str:
    s = max(0, round(seconds))
    if s < 90:
        return f"{s} s"
    if s < 90 * 60:
        return f"{round(s / 60)} min"
    if s < 48 * 3600:
        return f"{s // 3600} h {round((s % 3600) / 60)} min"
    return f"{s / 86400:.1f} zile"


def build_alert(threshold: int, pressure: float, clog_threshold: float,
                reading: dict | None, app_url: str, grafana_url: str) -> dict:
    """Everything the senders need: subject, plain text, HTML, push title/body."""
    lv = LEVELS[threshold]
    reading = reading or {}
    # Clogging stops at 100% - past the threshold the filter is simply clogged
    # (the pressure itself is still reported as measured)
    pct = min(pressure / clog_threshold * 100, 100) if clog_threshold else 0
    now = datetime.now(LOCAL_TZ).strftime("%d.%m.%Y, %H:%M")

    # Measurements that exist in this reading, in display order
    rows = [("Presiune diferențială", f"{pressure:.2f} bar (prag {clog_threshold:.2f})")]
    if reading.get("flow_rate_lmin") is not None:
        rows.append(("Debit", f"{float(reading['flow_rate_lmin']):.1f} L/min"))
    if reading.get("turbidity_ntu") is not None:
        rows.append(("Turbiditate", f"{float(reading['turbidity_ntu']):.2f} NTU"))
    days = reading.get("days_remaining_model")
    if threshold < 100 and days is not None and float(days) > 0:
        rows.append(("Estimare înfundare", f"în ~{_duration(float(days) * 86400)}"))

    # ---- plain text (fallback for clients without HTML) ----
    text = "\n".join(
        [lv["headline"] + f" ({pct:.0f}% înfundare)", "", lv["advice"], ""]
        + [f"{k}: {v}" for k, v in rows]
        + ["", f"Dashboard: {app_url}", f"Grafana: {grafana_url}", "", f"Water Filter Monitor · {now}"]
    )

    # ---- HTML email: tables + inline styles, the only layout mail clients agree on ----
    esc = html.escape
    bar = min(pct, 100)
    rows_html = "".join(
        f'<tr><td style="padding:7px 0;color:#6b7280;font-size:14px;border-bottom:1px solid #f3f4f6">{esc(k)}</td>'
        f'<td style="padding:7px 0;color:#111827;font-size:14px;font-weight:600;text-align:right;'
        f'border-bottom:1px solid #f3f4f6">{esc(v)}</td></tr>'
        for k, v in rows
    )
    html_body = f"""<!DOCTYPE html>
<html lang="ro"><body style="margin:0;padding:0;background:#f3f4f6;font-family:'Segoe UI',Roboto,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6">
<tr><td align="center" style="padding:24px 12px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:520px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">
    <tr><td style="background:{lv['color']};padding:18px 24px;color:#ffffff">
      <div style="font-size:13px;opacity:.9">&#128167; Water Filter Monitor</div>
      <div style="font-size:22px;font-weight:700;margin-top:4px">{esc(lv['headline'])}</div>
    </td></tr>
    <tr><td style="padding:22px 24px 8px">
      <p style="margin:0 0 16px;font-size:15px;line-height:1.5;color:#111827">{esc(lv['advice'])}</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="background:#e5e7eb;border-radius:999px"><tr>
        <td width="{bar:.0f}%" style="background:{lv['color']};height:10px;border-radius:999px;font-size:0;line-height:0">&nbsp;</td>
        <td style="font-size:0;line-height:0">&nbsp;</td>
      </tr></table>
      <p style="margin:6px 0 18px;font-size:13px;color:#6b7280">
        <span style="display:inline-block;padding:2px 8px;border-radius:999px;background:{lv['tint']};
              color:{lv['color']};font-weight:700">{pct:.0f}%</span>&nbsp; înfundare (pragul: presiune de {clog_threshold:.2f} bar)
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
    </td></tr>
    <tr><td style="padding:18px 24px 24px">
      <a href="{esc(app_url)}" style="display:inline-block;background:{lv['color']};color:#ffffff;
         padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">Deschide dashboard</a>
      &nbsp;
      <a href="{esc(grafana_url)}" style="display:inline-block;border:1px solid #d1d5db;color:#374151;
         padding:9px 16px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">Grafana</a>
    </td></tr>
    <tr><td style="padding:12px 24px;background:#f9fafb;font-size:12px;color:#9ca3af;border-top:1px solid #f3f4f6">
      Alertă automată · {esc(now)} · o singură notificare per prag, până la schimbarea filtrului.
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""

    # ---- ntfy push: short, like a real notification (markdown for the bold values) ----
    push_lines = [f"**{pct:.0f}%** înfundare · presiune **{pressure:.2f} bar**"]
    details = [f"{k} {v}" for k, v in rows[1:3] if k in ("Debit", "Turbiditate")]
    if details:
        push_lines.append(" · ".join(details))
    push_lines.append(lv["advice"])

    return {
        "subject": f"[Water Filter Monitor] {lv['subject']}",
        "text": text,
        "html": html_body,
        "push": {
            "title": lv["subject"],
            "message": "\n".join(push_lines),
            "priority": lv["priority"],
            "tags": [lv["tag"], "droplet"],
        },
    }
