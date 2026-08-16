# Senzor fizic (ESP32) - opțional, extensie hardware

Acest folder conține firmware-ul pentru un senzor fizic real, ca alternativă
(sau completare) la senzorul virtual din `sensor/main.py`. Publică pe același
topic MQTT (`home/water/filter`), cu format JSON compatibil - backend-ul
(`backend/mqtt_subscriber.py`) nu are nevoie de nicio modificare.

## Hardware necesar

| Componentă | Rol |
|---|---|
| ESP32 DevKit | microcontroler cu WiFi integrat |
| 2x senzor presiune analogic 0.5-4.5V | montați înainte și după filtru, prin divizor rezistiv (vezi comentariile din `.ino`) |
| Debitmetru cu impulsuri (YF-S201) | măsoară `flow_rate_lmin` |

Presiunea diferențială (`pressure_drop_bar`) se calculează în firmware ca
`presiune_înainte - presiune_după`, la fel cum modelul din senzorul virtual o
simulează.

## Pași de punere în funcțiune

1. Instalează în Arduino IDE (sau PlatformIO) librăriile `PubSubClient` și
   `ArduinoJson`, plus placa `esp32` (Boards Manager).
2. Deschide `water_filter_sensor/water_filter_sensor.ino`, completează
   `WIFI_SSID` / `WIFI_PASSWORD` și `MQTT_HOST` (IP-ul local al PC-ului tău,
   nu `localhost` - află-l cu `ipconfig`).
3. Verifică că Mosquitto din `docker-compose.yml` acceptă conexiuni din
   rețeaua locală (portul 1883 e deja expus).
4. Încarcă firmware-ul pe ESP32, deschide Serial Monitor la 115200 baud ca
   să vezi log-urile de conectare și publicare.
5. Verifică în Grafana / `curl http://localhost:8000/latest` că citirile
   fizice apar - exact ca la senzorul virtual.

## Acces de oriunde (varianta cloud)

Pentru a vedea datele fără să fii în aceeași rețea:

1. Creează un cont gratuit pe [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/),
   notează host-ul clusterului, portul TLS (8883) și credențialele.
2. În `.ino`: schimbă `WiFiClient` în `WiFiClientSecure`, `MQTT_HOST`/`MQTT_PORT`
   cu valorile HiveMQ, adaugă `MQTT_USER`/`MQTT_PASSWORD`.
3. Backend-ul trebuie să se aboneze la același broker cloud în loc de
   Mosquitto local (schimbare de configurare, nu de cod).
4. Pentru Grafana accesibil public, folosește
   [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
   (gratuit, fără port forwarding pe router).

**Nu urca niciodată parola de WiFi sau credențialele MQTT pe GitHub** - mută-le
într-un `config.h` separat și adaugă-l în `.gitignore`, la fel ca
`.env.secrets` din backend.
