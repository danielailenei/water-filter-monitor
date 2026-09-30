"""
Alerting: sends a notification (email + ntfy.sh push) when the filter's
clogging level crosses 80%, 90% or 100% of the clog threshold.

Each threshold fires once per filter cycle. If the pressure drops sharply
(filter replaced / sensor restarted) the thresholds reset so the next cycle
can alert again. Every send is retried a few times so a transient network
error does not silently drop an alert.

Which thresholds already fired is saved in InfluxDB (alert_event), so a
restart or redeploy of the worker does not notify the same cycle twice.

Configuration via environment variables (see .env.secrets.example):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO, NTFY_TOPIC
    APP_URL, GRAFANA_URL - public links put in the alerts (localhost by default)
"""

import os
import smtplib
import ssl
import time
from email.message import EmailMessage

import requests

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 3

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
# Gmail shows app passwords in 4 space-separated groups for readability; the
# actual secret is the 16 chars with no spaces. Strip them so a copy-paste of
# the displayed form still works.
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Where the alert links point: localhost for docker compose, the CloudFront
# address on AWS (set in the ECS task definition).
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000").rstrip("/")

THRESHOLDS = [80, 90, 100]
RESET_BELOW_PCT = 50  # below this we assume the filter was replaced


def _with_retry(description: str, func, attempts: int = RETRY_ATTEMPTS,
                delay: float = RETRY_DELAY_SECONDS) -> bool:
    """Retry an operation prone to transient network errors (e.g. a DNS hiccup
    inside the container). Without this, a few seconds of network loss can drop
    an alert for good."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            func()
            return True
        except Exception as e:
            last_error = e
            print(f"[alerting] attempt {attempt}/{attempts} for {description} failed: {e}")
            if attempt < attempts:
                time.sleep(delay)
    print(f"[alerting] {description} failed after {attempts} attempts: {last_error}")
    return False


class AlertManager:
    def __init__(self, store=None):
        # store: DBWriter (or anything with write_alert_event / get_fired_thresholds);
        # None keeps the state in memory only.
        self._store = store
        self._fired = set()  # thresholds already notified in the current cycle
        if store is not None:
            try:
                self._fired = store.get_fired_thresholds()
                print(f"[alerting] restored state: already notified {sorted(self._fired) or 'nothing'}")
            except Exception as e:
                print(f"[alerting] could not restore state, starting empty: {e}")

    def _record(self, kind: str, threshold: int = 0):
        if self._store is None:
            return
        try:
            self._store.write_alert_event(kind, threshold)
        except Exception as e:
            print(f"[alerting] could not save alert state: {e}")

    def reset(self):
        if self._fired:
            print("[alerting] filter reset (low pressure) - re-arming thresholds.")
            self._record("reset")
        self._fired.clear()

    def check_and_notify(self, pressure_drop_bar: float, clog_threshold_bar: float):
        if clog_threshold_bar <= 0:
            return
        pct = (pressure_drop_bar / clog_threshold_bar) * 100

        if pct < RESET_BELOW_PCT and self._fired:
            self.reset()

        for threshold in THRESHOLDS:
            if pct >= threshold and threshold not in self._fired:
                self._fired.add(threshold)
                self._record("sent", threshold)
                self._send_alert(threshold, pressure_drop_bar, clog_threshold_bar)

    def _send_alert(self, threshold: int, pressure_drop_bar: float, clog_threshold_bar: float):
        # Report the rounded threshold (80/90/100), not the raw pressure/threshold
        # ratio - the model has no upper bound after clogging, so that ratio can
        # read e.g. "5548%". Actual values go in the body, clearly labelled.
        if threshold >= 100:
            subject = "Water filter CLOGGED - replacement needed"
            emoji = "\U0001F534"
            advice = "The filter has reached full clogging. Replace it as soon as possible."
        elif threshold == 90:
            subject = "Water filter at 90% capacity"
            emoji = "\U0001F7E0"
            advice = "The filter is close to clogging. Have a replacement ready."
        else:
            subject = "Water filter at 80% capacity"
            emoji = "\U0001F7E1"
            advice = "The filter is clogging noticeably. Plan a replacement soon."

        body = (
            f"{emoji} The water filter has reached {threshold}% of its clogging capacity.\n\n"
            f"{advice}\n\n"
            f"Current differential pressure: {pressure_drop_bar:.2f} bar "
            f"(clog threshold: {clog_threshold_bar:.2f} bar)\n\n"
            f"Dashboard: {APP_URL}\n"
            f"Grafana: {GRAFANA_URL}"
        )

        self._send_email(subject, body)
        self._send_push(subject, body)

    def _send_email(self, subject: str, body: str):
        if not (SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL_TO):
            print("[alerting] email not configured - skipping.")
            return

        def _do_send():
            msg = EmailMessage()
            msg["Subject"] = f"[Water Filter Monitor] {subject}"
            msg["From"] = SMTP_USER
            msg["To"] = ALERT_EMAIL_TO
            msg.set_content(body)
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

        if _with_retry(f"email '{subject}'", _do_send):
            print(f"[alerting] email sent: {subject}")

    def _send_push(self, subject: str, body: str):
        if not NTFY_TOPIC:
            print("[alerting] ntfy not configured - skipping.")
            return

        def _do_send():
            response = requests.post(
                NTFY_URL,
                data=body.encode("utf-8"),
                headers={
                    "Title": subject.encode("utf-8"),
                    "Priority": "urgent" if "CLOGGED" in subject else "default",
                    "Tags": "droplet",
                    # Tapping the notification opens the dashboard; a button opens Grafana
                    "Click": APP_URL,
                    "Actions": f"view, Grafana, {GRAFANA_URL}",
                },
                timeout=5,
            )
            response.raise_for_status()

        if _with_retry(f"push '{subject}'", _do_send):
            print(f"[alerting] push sent: {subject}")
