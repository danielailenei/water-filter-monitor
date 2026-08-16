"""
Modul de alertare: trimite notificari (email + push, prin ntfy.sh) atunci
cand nivelul de colmatare al filtrului (raportat ca procent din pragul de
infundare) trece de anumite praguri (80%, 90%, 100%).

Fiecare prag este notificat o singura data per "ciclu" al filtrului -
daca presiunea scade brusc (filtru "inlocuit"/senzor repornit), pragurile
se reseteaza automat, pentru ca urmatorul ciclu sa poata genera din nou
alertele.

Trimiterea (email si push) foloseste reincercare automata (3 incercari,
cu pauza intre ele), ca o intrerupere tranzitorie de retea (de exemplu un
hiccup DNS in interiorul containerului) sa nu piarda definitiv o alerta.

Configurare prin variabile de mediu (vezi docker-compose.yml si
.env.secrets.example):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO
    NTFY_TOPIC
"""

import os
import smtplib
import ssl
import time
from email.message import EmailMessage

import requests

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 3


def _with_retry(description: str, func, attempts: int = RETRY_ATTEMPTS, delay: float = RETRY_DELAY_SECONDS) -> bool:
    """
    Reincearca o operatie predispusa la erori tranzitorii de retea (de
    exemplu, un hiccup DNS in interiorul containerului Docker - vezi
    sectiunea 4.7 din lucrare). Fara aceasta reincercare, o singura
    intrerupere de cateva secunde a retelei poate pierde definitiv o
    alerta (observat concret: pragurile de 90% si 100% nu au putut fi
    livrate din cauza unei erori "No address associated with hostname",
    aparuta chiar cand cele trei praguri s-au declansat aproape simultan).
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            func()
            return True
        except Exception as e:
            last_error = e
            print(f"[alerting] Incercarea {attempt}/{attempts} pentru {description} a esuat: {e}")
            if attempt < attempts:
                time.sleep(delay)
    print(f"[alerting] {description} a esuat definitiv dupa {attempts} incercari: {last_error}")
    return False

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

THRESHOLDS = [80, 90, 100]
RESET_BELOW_PCT = 50  # sub acest procent, consideram ca filtrul a fost inlocuit


class AlertManager:
    def __init__(self):
        self._fired = set()  # praguri deja notificate in ciclul curent al filtrului

    def reset(self):
        if self._fired:
            print("[alerting] Filtru resetat (presiune scazuta) - repornesc pragurile de alerta.")
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
                self._send_alert(threshold, pressure_drop_bar, clog_threshold_bar)

    def _send_alert(self, threshold: int, pressure_drop_bar: float, clog_threshold_bar: float):
        # Procentul afisat in notificare este intotdeauna pragul rotund
        # (80/90/100), NU raportul brut presiune/prag - acela poate depasi
        # cu mult 100% (modelul de degradare al senzorului nu limiteaza
        # superior presiunea dupa infundare, vezi sectiunea 3.1.1), ceea
        # ce ar produce mesaje confuze de genul "5548%". Valorile reale
        # (presiune curenta si prag), utile tehnic, sunt incluse separat,
        # clar etichetate, in corpul mesajului.
        if threshold >= 100:
            subject = "Filtru de apa INFUNDAT - inlocuire necesara"
            emoji = "\U0001F534"  # cerc rosu
            recomandare = (
                "Filtrul a atins pragul complet de colmatare. Se recomanda "
                "inlocuirea lui cat mai curand posibil."
            )
        elif threshold == 90:
            subject = "Filtru de apa la 90% din capacitate"
            emoji = "\U0001F7E0"  # cerc portocaliu
            recomandare = (
                "Filtrul este aproape de pragul de infundare. Pregateste un "
                "filtru de schimb - inlocuirea va fi necesara in curand."
            )
        else:
            subject = "Filtru de apa la 80% din capacitate"
            emoji = "\U0001F7E1"  # cerc galben
            recomandare = (
                "Filtrul a inceput sa se colmateze semnificativ. Ia in calcul "
                "planificarea unei inlocuiri in perioada urmatoare."
            )

        body = (
            f"{emoji} Filtrul de apa a atins {threshold}% din capacitatea de colmatare.\n\n"
            f"{recomandare}\n\n"
            f"Presiune diferentiala curenta: {pressure_drop_bar:.2f} bar "
            f"(prag de infundare: {clog_threshold_bar:.2f} bar)\n\n"
            f"Verifica dashboard-ul Grafana pentru detalii: http://localhost:3000"
        )

        self._send_email(subject, body)
        self._send_push(subject, body)

    def _send_email(self, subject: str, body: str):
        if not (SMTP_USER and SMTP_PASSWORD and ALERT_EMAIL_TO):
            print("[alerting] Email neconfigurat (lipsesc credentiale) - sar peste.")
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
            print(f"[alerting] Email trimis: {subject}")

    def _send_push(self, subject: str, body: str):
        if not NTFY_TOPIC:
            print("[alerting] ntfy neconfigurat (lipseste topic) - sar peste.")
            return

        def _do_send():
            response = requests.post(
                NTFY_URL,
                data=body.encode("utf-8"),
                headers={
                    "Title": subject.encode("utf-8"),
                    "Priority": "urgent" if "INFUNDAT" in subject else "default",
                    "Tags": "droplet",
                },
                timeout=5,
            )
            response.raise_for_status()

        if _with_retry(f"push '{subject}'", _do_send):
            print(f"[alerting] Push trimis: {subject}")


alert_manager = AlertManager()
