# Versiune fixata (nu "latest") -> build reproductibil
FROM grafana/grafana:13.1.3

# Patch de securitate: scanarea ECR a gasit CVE-uri CRITICAL/HIGH in curl 8.21.0
# si openssl 3.5.7 din baza Alpine. Alpine are deja versiunile corectate
# (curl 8.22.0, openssl 3.5.8). Actualizam DOAR aceste pachete (schimbare minima),
# ca root, apoi revenim la utilizatorul neprivilegiat al imaginii (472 = grafana).
USER root
RUN apk upgrade --no-cache curl libcurl libssl3 libcrypto3
USER 472

# Ora Romaniei si format romanesc de data (ca dashboard-ul aplicatiei si email-urile),
# oricare ar fi fusul orar al containerului (UTC) sau al browserului.
ENV GF_DATE_FORMATS_DEFAULT_TIMEZONE=Europe/Bucharest \
    GF_DATE_FORMATS_DEFAULT_WEEK_START=monday \
    GF_DATE_FORMATS_FULL_DATE="DD.MM.YYYY HH:mm:ss" \
    GF_DATE_FORMATS_INTERVAL_SECOND="HH:mm:ss" \
    GF_DATE_FORMATS_INTERVAL_MINUTE="HH:mm" \
    GF_DATE_FORMATS_INTERVAL_HOUR="DD.MM HH:mm" \
    GF_DATE_FORMATS_INTERVAL_DAY="DD.MM" \
    GF_DATE_FORMATS_INTERVAL_MONTH="MM.YYYY" \
    GF_DATE_FORMATS_INTERVAL_YEAR="YYYY"

# Datasource-ul InfluxDB si dashboard-ul, provizionate la pornire.
# Token-ul InfluxDB vine din variabila de mediu INFLUX_TOKEN (din SSM), nu din fisier.
COPY provisioning /etc/grafana/provisioning
