# Versiune fixata (nu "latest") -> build reproductibil
FROM grafana/grafana:13.1.3

# Patch de securitate: scanarea ECR a gasit CVE-uri CRITICAL/HIGH in curl 8.21.0
# si openssl 3.5.7 din baza Alpine. Alpine are deja versiunile corectate
# (curl 8.22.0, openssl 3.5.8). Actualizam DOAR aceste pachete (schimbare minima),
# ca root, apoi revenim la utilizatorul neprivilegiat al imaginii (472 = grafana).
USER root
RUN apk upgrade --no-cache curl libcurl libssl3 libcrypto3
USER 472

# Datasource-ul InfluxDB si dashboard-ul, provizionate la pornire.
# Token-ul InfluxDB vine din variabila de mediu INFLUX_TOKEN (din SSM), nu din fisier.
COPY provisioning /etc/grafana/provisioning
