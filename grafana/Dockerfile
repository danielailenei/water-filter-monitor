# Versiune fixata (nu "latest") -> build reproductibil
FROM grafana/grafana:13.1.3

# Datasource-ul InfluxDB si dashboard-ul, provizionate la pornire.
# Token-ul InfluxDB vine din variabila de mediu INFLUX_TOKEN (din SSM), nu din fisier.
COPY provisioning /etc/grafana/provisioning
