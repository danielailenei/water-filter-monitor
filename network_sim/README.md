# network_sim — simularea de rețea (ns-3)

Componentă opțională, rulată **separat**, în WSL2, care produce un fișier
CSV cu latențe realiste (obținute dintr-o simulare de rețea reală, cu
ns-3), pe care senzorul virtual le poate reproduce ca delay înainte de
fiecare `publish()` MQTT — demonstrând impactul rețelei asupra timpului de
livrare a datelor.

## Ce conține folderul

| Fișier | Rol |
|---|---|
| [`ns3_config/iot_water_filter_scenario.cc`](ns3_config/iot_water_filter_scenario.cc) | Scenariul ns-3: N senzori → AP → server, prin o legătură "backhaul" parametrizabilă |
| [`xml_to_csv.py`](xml_to_csv.py) | Convertește rezultatele FlowMonitor (XML) în CSV `packet_id,latency_ms` |
| `latency_output.csv` | CSV-ul citit de `sensor/virtual_sensor.py` (înlocuit cu rezultate reale, vezi mai jos) |

## Topologia simulată

```
senzor_0 ─┐
senzor_1 ─┤                    legatura "backhaul"
senzor_2 ─┼── AP (hub) ──────────────────────────── Server
senzor_3 ─┤   star, 100Mbps/1ms                    (dataRate, delay si
senzor_4 ─┤   (local, gen WiFi/LAN)                  marimea cozii sunt
senzor_5 ─┘                                          parametri de linie
                                                       de comanda)
```

Fiecare senzor trimite pachete UDP mici, periodic, către server. Legătura
"backhaul" (AP → Server) e cea pe care o variem între rulări, ca să
comparăm scenarii diferite (ex. rețea rapidă tip 5G vs. rețea congestionată
tip WiFi/4G suprasolicitat).

## Pas cu pas — de la simulare la CSV

Presupune ns-3 deja instalat și compilat în WSL2, la `~/ns-3` (build de
tip `./ns3 configure --enable-examples && ./ns3 build`, cu modulele
implicite — nu e nevoie de niciun modul extra pentru acest scenariu).

**1. Copiază scenariul în ns-3** (dintr-un terminal WSL, în interiorul
distribuției `Ubuntu`):

```bash
cp /mnt/c/Users/Daniel/Desktop/water-filter-monitor/network_sim/ns3_config/iot_water_filter_scenario.cc \
   ~/ns-3/scratch/iot_water_filter_scenario.cc
```

**2. Rulează simularea, o dată pentru fiecare scenariu de interes.**
Exemplu — o rețea rapidă ("5G-like") și una congestionată:

```bash
cd ~/ns-3

./ns3 run "iot_water_filter_scenario \
  --backhaulDataRate=50Mbps --backhaulDelay=10ms --backhaulQueueSize=20 \
  --outputXml=scenario_5g.xml"

./ns3 run "iot_water_filter_scenario \
  --backhaulDataRate=5Mbps --backhaulDelay=40ms --backhaulQueueSize=10 \
  --outputXml=scenario_congestionat.xml"
```

Parametri disponibili (toți opționali, cu valori implicite rezonabile):
`numSensors`, `simTime`, `packetInterval`, `packetSize`,
`backhaulDataRate`, `backhaulDelay`, `backhaulQueueSize`, `outputXml`.

**3. Convertește XML-ul rezultat în CSV**, cu scriptul din acest folder:

```bash
python3 /mnt/c/Users/Daniel/Desktop/water-filter-monitor/network_sim/xml_to_csv.py \
  ~/ns-3/scenario_5g.xml \
  /mnt/c/Users/Daniel/Desktop/water-filter-monitor/network_sim/latency_output.csv
```

(pentru scenariul congestionat, rulezi din nou, cu alt fișier de ieșire,
ex. `latency_congestionat.csv`, ca să le poți compara pe amândouă).

**4. Activează delay-ul de rețea în senzorul virtual** — în
`sensor/config.yaml`:

```yaml
network:
  use_latency_file: true
  latency_file: ../network_sim/latency_output.csv
```

Repornește `python virtual_sensor.py` — acum fiecare publicare MQTT va
aștepta un delay real, extras din simularea ns-3, înainte de a trimite
citirea.

## De ce histogram, nu latență exactă per pachet

FlowMonitor din ns-3 nu salvează latența fiecărui pachet individual, ci un
**histogram** (câte pachete au avut latența într-un anumit interval, ex.
"între 10 și 11 ms au fost 4 pachete"). `xml_to_csv.py` reconstruiește din
acest histogram o listă aproximativă de latențe per pachet (fiecare pachet
dintr-un bin primește valoarea de mijloc a bin-ului, plus un mic zgomot) —
o aproximare standard, suficient de fidelă distribuției reale pentru
scopul demonstrației, și mult mai simplă decât instrumentarea manuală a
fiecărui pachet cu trace sink-uri proprii.
