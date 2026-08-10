# Water Filter Monitor — Documentație completă

> Sistem IoT simulat pentru monitorizarea în timp real a stării unui filtru de
> apă și predicția momentului de înfundare. Documentul de față descrie
> arhitectura sistemului, rolul fiecărei componente, legăturile dintre ele și
> un tutorial pas cu pas de instalare și utilizare, scris pentru cineva care
> nu a mai folosit aplicația până acum.

## Cuprins

1. [Scopul aplicației](#1-scopul-aplicației)
2. [Arhitectura generală](#2-arhitectura-generală)
3. [Componentele sistemului, în detaliu](#3-componentele-sistemului-în-detaliu)
   - 3.1 [Senzorul virtual](#31-senzorul-virtual-sensor)
   - 3.2 [Broker-ul MQTT — Mosquitto](#32-broker-ul-mqtt--mosquitto)
   - 3.3 [Backend-ul — FastAPI](#33-backend-ul--fastapi)
   - 3.4 [Baza de date — InfluxDB](#34-baza-de-date--influxdb)
   - 3.5 [Vizualizarea — Grafana](#35-vizualizarea--grafana)
   - 3.6 [Simularea de rețea — ns-3 / Simu5G](#36-simularea-de-rețea--ns-3--simu5g)
4. [Fluxul complet al unei citiri](#4-fluxul-complet-al-unei-citiri)
5. [Legăturile dintre servicii](#5-legăturile-dintre-servicii)
6. [Tutorial de instalare și utilizare, pas cu pas](#6-tutorial-de-instalare-și-utilizare-pas-cu-pas)
7. [Depanare — probleme frecvente și soluții](#7-depanare--probleme-frecvente-și-soluții)
8. [Argumentarea alegerilor tehnice (pentru disertație)](#8-argumentarea-alegerilor-tehnice-pentru-disertație)
9. [Fișă rapidă de comenzi](#9-fișă-rapidă-de-comenzi)

---

## 1. Scopul aplicației

Aplicația simulează un senzor IoT montat pe un filtru de apă (de exemplu
dintr-un sistem de osmoză inversă sau un filtru casnic) care măsoară în
timp real:

- **presiunea diferențială** dintre intrarea și ieșirea filtrului (bar);
- **debitul de apă** care trece prin filtru (L/min);
- **turbiditatea** apei filtrate (NTU — unitate standard de turbiditate).

Pe măsură ce filtrul se colmatează (se înfundă cu impurități), presiunea
diferențială crește, debitul scade, iar turbiditatea crește ușor. Sistemul
colectează aceste date, le stochează istoric, le afișează pe un dashboard
live și estimează — pe baza unui model statistic — **peste câte zile
filtrul se va înfunda complet**, astfel încât utilizatorul să știe din timp
când trebuie să-l schimbe.

Pentru că nu există un filtru fizic instrumentat, întregul senzor este
**simulat în software** (`sensor/virtual_sensor.py`), pornind de la un model
matematic de degradare. Restul arhitecturii (comunicație, stocare,
predicție, vizualizare) este identică cu ce s-ar folosi și pentru un senzor
fizic real — asta face demonstrația relevantă pentru un sistem IoT real.

---

## 2. Arhitectura generală

```
 ┌──────────────────┐        MQTT         ┌───────────────────────┐
 │  Senzor virtual   │ ───publish────────▶ │  Mosquitto (broker)   │
 │  (Python, rulează │   topic:            │  port 1883            │
 │  local, cu Python │   home/water/filter │                       │
 │  instalat pe PC)  │                     └───────────┬───────────┘
 └──────────────────┘                                  │ subscribe
        ▲                                               ▼
        │ delay de rețea               ┌──────────────────────────────┐
        │ simulat (opțional,           │  Backend FastAPI (Docker)     │
        │ din CSV exportat din         │  - mqtt_subscriber.py         │
        │ ns-3 / Simu5G, WSL2)         │  - db_writer.py                │
        │                              │  - ml_model.py (predicție)     │
        │                              │  - main.py (API REST)          │
        │                              └───────┬───────────────┬───────┘
        │                                      │ scrie puncte  │ expune
        │                                      ▼               ▼ REST
        │                          ┌────────────────────┐   http://localhost:8000
        │                          │  InfluxDB (Docker)  │   /health /latest
        │                          │  bucket water_filter│   /history /predict
        │                          └──────────┬──────────┘
        │                                     │ interoghează (Flux)
        │                                     ▼
        │                          ┌────────────────────┐
        └──────────────────────── │  Grafana (Docker)   │  http://localhost:3000
      network_sim/latency_output.csv          dashboard live
      (rulat separat, opțional)
```

**Pe scurt:** senzorul virtual "vorbește" MQTT, un broker (Mosquitto)
transportă mesajele, backend-ul le ascultă și le scrie într-o bază de date
de tip serie-de-timp (InfluxDB), iar Grafana citește din aceeași bază de
date pentru a desena grafice live. Backend-ul mai expune și un API propriu
(REST) prin care poți cere direct ultima citire, istoricul sau o predicție.

Patru din cele cinci componente (Mosquitto, InfluxDB, backend, Grafana)
rulează în containere Docker, pornite dintr-o singură comandă
(`docker compose up`). Senzorul virtual rulează separat, direct cu Python pe
Windows — alegere deliberată, ca să poată fi oprit/pornit/modificat rapid în
timpul dezvoltării, fără să reconstruiești imagini Docker.

---

## 3. Componentele sistemului, în detaliu

### 3.1 Senzorul virtual (`sensor/`)

**Ce face:** generează, la fiecare câteva secunde, o citire nouă (presiune,
debit, turbiditate) și o trimite prin MQTT.

**Fișiere:**

| Fișier | Rol |
|---|---|
| [`filter_model.py`](../sensor/filter_model.py) | Modelul matematic al degradării filtrului |
| [`virtual_sensor.py`](../sensor/virtual_sensor.py) | Bucla principală: calculează citiri, publică pe MQTT |
| [`config.yaml`](../sensor/config.yaml) | Parametrii simulării (viteză colmatare, interval publicare etc.) |
| [`requirements.txt`](../sensor/requirements.txt) | Dependențe Python (`paho-mqtt`, `PyYAML`) |

**Modelul matematic** (`filter_model.py`), explicat:

Un filtru care se colmatează urmează, aproximativ, o creștere **exponențială**
a presiunii diferențiale în timp:

```
presiune(t) = presiune_de_bază · e^(k · t)
```

unde `k` este `clogging_rate` (rata de colmatare) și `t` este timpul scurs
(în ore de simulare, accelerat). Debitul scade invers proporțional cu
presiunea:

```
debit(t) = debit_de_bază / (1 + presiune(t))
```

iar turbiditatea crește liniar, ușor, odată cu presiunea. Peste fiecare
valoare se adaugă un mic zgomot aleator (`random.uniform`), ca datele să
semene cu măsurători reale de senzor, nu cu o linie matematică perfectă.

Filtrul este considerat **înfundat** (`is_clogged = true`) când presiunea
diferențială depășește `clog_threshold_bar` (implicit 1.5 bar).

Fiindcă în realitate colmatarea completă durează luni de zile, simularea
**accelerează timpul** printr-un factor `time_acceleration` (implicit 500):
o oră reală de rulare a senzorului corespunde la 500 de ore simulate de
funcționare a filtrului. Cu setările implicite, filtrul se înfundă complet
în aproximativ **5 ore reale** de la pornirea senzorului — suficient de
rapid pentru o demonstrație, dar suficient de lent ca să poți urmări
evoluția graficelor pas cu pas.

**Bucla principală** (`virtual_sensor.py`):

1. Citește parametrii din `config.yaml`.
2. La fiecare `publish_interval_seconds` (implicit 5 secunde):
   - calculează o citire nouă folosind `FilterModel`;
   - (opțional, dacă `network.use_latency_file: true`) așteaptă un delay
     citit ciclic din `network_sim/latency_output.csv`, simulând latența
     unei rețele reale (ex. 5G) între senzor și server;
   - publică citirea ca JSON pe topicul MQTT `home/water/filter`;
   - afișează citirea și în consolă, pentru vizualizare directă.
3. Rulează la nesfârșit, până apeși `Ctrl+C`.

### 3.2 Broker-ul MQTT — Mosquitto

**Ce face:** este "poștașul" care transportă mesajele de la senzor la
backend. MQTT este protocolul standard de facto pentru comunicație IoT —
ușor, eficient, potrivit pentru dispozitive cu resurse limitate.

Rulează în container Docker (`eclipse-mosquitto:2`), ascultă pe portul
**1883**, configurat prin [`mosquitto/config/mosquitto.conf`](../mosquitto/config/mosquitto.conf)
(conexiuni anonime permise — potrivit pentru mediul de dezvoltare local, nu
și pentru producție). Senzorul **publică** pe topicul `home/water/filter`,
iar backend-ul **se abonează** (subscribe) la același topic.

### 3.3 Backend-ul — FastAPI (`backend/`)

**Ce face:** este "creierul" aplicației — ascultă mesajele MQTT, le scrie
persistent în baza de date, și expune un API REST prin care orice client
(Grafana, un browser, un script de testare) poate întreba sistemul despre
starea filtrului.

| Fișier | Rol |
|---|---|
| [`main.py`](../backend/main.py) | Aplicația FastAPI, punctul de intrare, endpoint-urile REST |
| [`mqtt_subscriber.py`](../backend/mqtt_subscriber.py) | Se conectează la Mosquitto, primește citirile, le scrie în InfluxDB |
| [`db_writer.py`](../backend/db_writer.py) | Wrapper peste clientul InfluxDB — scriere puncte + interogare istoric |
| [`ml_model.py`](../backend/ml_model.py) | Modelul de predicție "câte zile mai are filtrul" |
| [`Dockerfile`](../backend/Dockerfile) | Rețeta de construire a imaginii Docker a backend-ului |
| [`requirements.txt`](../backend/requirements.txt) | Dependențe Python (FastAPI, InfluxDB client, scikit-learn etc.) |

**Endpoint-urile REST** (toate accesibile la `http://localhost:8000`):

| Endpoint | Descriere |
|---|---|
| `GET /health` | Verificare rapidă că backend-ul e sus — răspunde `{"status":"ok"}` |
| `GET /latest` | Ultima citire primită prin MQTT (din memorie, nu din bază de date) |
| `GET /history?hours=24` | Toate citirile din InfluxDB din ultimele `hours` ore |
| `GET /predict?hours=24` | Predicția "zile rămase până la înfundare", calculată din istoricul din ultimele `hours` ore |

**Modelul de predicție** (`ml_model.py`), explicat:

Presiunea diferențială crește exponențial (`presiune = bază · e^(k·t)`),
ceea ce înseamnă că **logaritmul** presiunii crește **liniar** în timp:

```
ln(presiune(t)) = ln(bază) + k · t
```

Backend-ul ia istoricul recent de citiri din InfluxDB, calculează
`ln(presiune)` pentru fiecare punct, și potrivește o **regresie liniară**
(`scikit-learn`, `LinearRegression`) peste aceste puncte. Din panta dreptei
rezultate (`k`, rata de degradare) și punctul curent, extrapolează
matematic **timpul până când presiunea va atinge pragul de înfundare**
(1.5 bar implicit), și îl convertește în zile.

Avantajul acestei abordări față de o rețea neuronală: e simplă,
interpretabilă (raportează și `R²`, adică cât de bine se potrivește
dreapta pe date — util de discutat la susținerea disertației), și
funcționează la fel de bine pe date simulate sau pe citiri reale de la un
senzor fizic, dacă sistemul ar fi extins ulterior.

### 3.4 Baza de date — InfluxDB

**Ce face:** stochează istoricul complet al citirilor. InfluxDB este o bază
de date specializată pentru **serii de timp** (time-series) — potrivită
pentru date de senzori, cu frecvență mare de scriere și interogări pe
intervale temporale.

Rulează în container Docker (`influxdb:2.7`), portul **8086**. La prima
pornire se auto-configurează cu:

- organizație: `disertatie`
- bucket (echivalentul unei baze de date): `water_filter`
- utilizator admin: `admin` / `admin12345`
- token de acces: `dev-super-secret-token`

Fiecare citire este scrisă ca un **punct** în measurement-ul
`filter_reading`, cu 4 câmpuri: `pressure_drop_bar`, `flow_rate_lmin`,
`turbidity_ntu`, `is_clogged`. Interogările se fac în limbajul **Flux**
(nativ InfluxDB 2.x).

Interfața web InfluxDB e disponibilă la `http://localhost:8086` — utilă
pentru a inspecta datele brute direct, fără Grafana.

### 3.5 Vizualizarea — Grafana

**Ce face:** desenează grafice live din datele stocate în InfluxDB.

Rulează în container Docker (`grafana/grafana:latest`), portul **3000**,
login implicit `admin` / `admin`. La pornire, Grafana se **auto-configurează**
(provisioning) din fișierele din [`grafana/provisioning/`](../grafana/provisioning/):

- `datasources/influxdb.yaml` — conectează Grafana la InfluxDB automat (nu
  trebuie configurat manual din interfață);
- `dashboards/water_filter_dashboard.json` — dashboard-ul gata construit,
  cu 4 panouri:
  1. **Cădere de presiune (bar)** — grafic linie, în timp;
  2. **Debit (L/min)** — grafic linie, în timp;
  3. **Turbiditate (NTU)** — grafic linie, în timp;
  4. **Filtru înfundat? (ultima citire)** — indicator text ("OK" verde /
     "INFUNDAT" roșu), bazat pe ultima valoare `is_clogged`.

Dashboard-ul se reîmprospătează automat la fiecare 5 secunde.

### 3.6 Simularea de rețea — ns-3 / Simu5G

**Ce face:** componentă opțională, gândită să demonstreze impactul unei
rețele reale (de exemplu 5G) asupra timpului de livrare a datelor de la
senzor la server.

Nu este integrată live cu restul sistemului (ar complica arhitectura fără
beneficiu real pentru scopul disertației). În schimb, fluxul e:

1. Rulezi separat o simulare **ns-3** (eventual cu modulul **Simu5G**) în
   **WSL2**, pentru un scenariu cu dispozitive IoT care trimit pachete către
   o stație de bază.
2. Exporți latențele rezultate într-un fișier CSV,
   [`network_sim/latency_output.csv`](../network_sim/latency_output.csv)
   (format: `packet_id,latency_ms`).
3. În `sensor/config.yaml`, setezi `network.use_latency_file: true` —
   senzorul virtual citește acest CSV ciclic și aplică fiecare latență ca
   delay real înainte de a publica pe MQTT.

Detalii complete despre cum se generează fișierul CSV din ns-3 sunt în
[`network_sim/README.md`](../network_sim/README.md).

---

## 4. Fluxul complet al unei citiri

```
1. virtual_sensor.py calculează o citire nouă (presiune, debit, turbiditate)
                            │
2. (opțional) așteaptă delay-ul de rețea simulat din latency_output.csv
                            │
3. publică JSON pe MQTT, topic "home/water/filter"  ──▶  Mosquitto (port 1883)
                            │
4. mqtt_subscriber.py (din backend) primește mesajul prin subscribe
                            │
5. db_writer.py scrie citirea ca punct în InfluxDB (bucket water_filter)
                            │
       ┌────────────────────┴────────────────────┐
       ▼                                          ▼
6a. Grafana interoghează InfluxDB          6b. Un client cheamă
    direct (Flux) și desenează                REST-ul backend-ului:
    graficele, la fiecare 5s                   /latest, /history, /predict
```

---

## 5. Legăturile dintre servicii

Tabelul de mai jos rezumă cine vorbește cu cine, pe ce port, și unde e
configurată legătura respectivă:

| De la | La | Protocol / Port | Unde e configurat |
|---|---|---|---|
| Senzor virtual | Mosquitto | MQTT / 1883 | `sensor/config.yaml` → `mqtt.broker: localhost` |
| Mosquitto | Backend | MQTT / 1883 | `backend/mqtt_subscriber.py`, variabile `MQTT_BROKER` în `docker-compose.yml` |
| Backend | InfluxDB | HTTP (Flux) / 8086 | `backend/db_writer.py`, variabile `INFLUX_*` în `docker-compose.yml` |
| Grafana | InfluxDB | HTTP (Flux) / 8086 | `grafana/provisioning/datasources/influxdb.yaml` |
| Client extern (browser, curl) | Backend | HTTP (REST) / 8000 | `backend/main.py` |
| Client extern (browser) | Grafana | HTTP / 3000 | — |
| Client extern (browser) | InfluxDB UI | HTTP / 8086 | — |

Toate cele 4 servicii Docker (mosquitto, influxdb, backend, grafana) rulează
în aceeași rețea Docker internă (creată automat de `docker-compose.yml`) și
se găsesc unele pe altele după **numele serviciului** (ex. backend-ul se
conectează la `mosquitto:1883`, nu la `localhost:1883` — asta funcționează
doar între containere). Senzorul virtual, rulând direct pe Windows (nu în
Docker), se conectează la `localhost:1883`, fiindcă portul e expus către
mașina gazdă prin `docker-compose.yml` (`ports: - "1883:1883"`).

---

## 6. Tutorial de instalare și utilizare, pas cu pas

Acest tutorial presupune că pornești de la zero, pe Windows, fără nimic
instalat. Fiecare pas explică ce faci și de ce.

### Pasul 0 — Ce trebuie să ai instalat

- **Docker Desktop** (cu motorul WSL2) — rulează 4 din cele 5 componente.
- **Python 3.10+** — pentru senzorul virtual, care rulează direct pe Windows.

Dacă nu le ai, pașii 1 și 2 te ghidează cum să le instalezi.

### Pasul 1 — Instalarea și pornirea Docker Desktop

1. Descarcă și instalează Docker Desktop de pe
   [docker.com](https://www.docker.com/products/docker-desktop/).
2. La prima pornire, Docker Desktop are nevoie de **WSL2** (Windows
   Subsystem for Linux) ca motor de rulare. Dacă la pornire primești o
   eroare legată de virtualizare sau WSL2, deschide PowerShell **ca
   Administrator** și rulează:

   ```bash
   wsl --install --no-distribution
   ```

   apoi **repornește PC-ul**. (Vezi și secțiunea [Depanare](#7-depanare--probleme-frecvente-și-soluții)
   de mai jos, dacă întâmpini erori specifice.)

3. Deschide Docker Desktop și așteaptă până indicatorul din stânga-jos arată
   verde ("Engine running").
4. Testează că funcționează, într-un terminal PowerShell:

   ```bash
   docker run hello-world
   ```

   Dacă vezi un mesaj de bun venit de la Docker, ești gata de pasul următor.

### Pasul 2 — Instalarea Python

Senzorul virtual rulează direct pe Windows (nu în Docker), deci ai nevoie
de Python instalat real (nu stub-ul din Microsoft Store).

```bash
winget install Python.Python.3.12
```

**Important:** după instalare, **închide și redeschide** fereastra
PowerShell (ca să se actualizeze PATH-ul), apoi verifică:

```bash
python --version
pip --version
```

### Pasul 3 — Obținerea proiectului

Copiază/clonează folderul `water-filter-monitor` pe discul tău (dacă citești
acest document, deja îl ai — de exemplu la
`C:\Users\<utilizator>\Desktop\water-filter-monitor`).

### Pasul 4 — Pornirea stack-ului Docker (Mosquitto, InfluxDB, backend, Grafana)

Deschide un terminal PowerShell, navighează în folderul proiectului, și
rulează:

```bash
cd C:\Users\<utilizator>\Desktop\water-filter-monitor
docker compose up --build
```

Prima rulare durează câteva minute (descarcă imaginile Docker și
construiește imaginea backend-ului). Vei vedea multe linii de log — e
normal. La final, ar trebui să vezi linii de tipul:

```
backend    | INFO:     Application startup complete.
backend    | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Lasă acest terminal deschis și rulând** — aici vezi log-urile live ale
tuturor serviciilor. Pentru comenzile următoare, deschide o **fereastră
PowerShell nouă**.

### Pasul 5 — Verificarea că totul e sus

În terminalul nou:

```bash
docker compose ps
```

Ar trebui să vezi 4 containere (`mosquitto`, `influxdb`, `backend`,
`grafana`), toate cu status `Up`.

Verifică backend-ul:

```bash
curl.exe http://localhost:8000/health
```

Ar trebui să răspundă `{"status":"ok"}`.

### Pasul 6 — Pornirea senzorului virtual

Tot în terminalul nou:

```bash
cd C:\Users\<utilizator>\Desktop\water-filter-monitor\sensor
pip install -r requirements.txt
python virtual_sensor.py
```

Vei vedea în consolă linii de tipul:

```
[*] Senzor virtual pornit. Public pe topicul 'home/water/filter' la fiecare 5s (timp accelerat x500).
Trimis: {'timestamp': ..., 'pressure_drop_bar': 0.2, 'flow_rate_lmin': 12.8, 'turbidity_ntu': 0.9, 'is_clogged': False, ...}
```

Asta înseamnă că senzorul trimite date cu succes. **Lasă și acest terminal
deschis** — reprezintă senzorul "conectat" în permanență.

### Pasul 7 — Verificarea datelor primite de backend

Într-un al treilea terminal (sau oricare altul liber):

```bash
curl.exe http://localhost:8000/latest
```

Ar trebui să arate exact ultima citire trimisă de senzor.

### Pasul 8 — Vizualizarea dashboard-ului în Grafana

1. Deschide un browser și navighează la **http://localhost:3000**.
2. Autentifică-te cu utilizator `admin`, parolă `admin` (poți sări peste
   solicitarea de schimbare a parolei, apăsând "Skip", pentru mediul local
   de dezvoltare).
3. În meniul din stânga, mergi la **Dashboards → Water Filter Monitor**
   (ar trebui să apară deja acolo, provizionat automat).
4. Vei vedea 4 panouri, care se actualizează la fiecare 5 secunde:
   - **Cădere de presiune (bar)** — crește lent, exponențial.
   - **Debit (L/min)** — scade lent.
   - **Turbiditate (NTU)** — crește ușor.
   - **Filtru înfundat?** — arată "OK" (verde) cât timp presiunea e sub
     prag, și "INFUNDAT" (roșu) după ce filtrul se colmatează.

### Pasul 9 — Cererea unei predicții

```bash
curl.exe http://localhost:8000/predict
```

Răspunsul arată câte zile mai are filtrul până la înfundare, pe baza
tendinței observate în istoric (are nevoie de câteva citiri acumulate ca să
fie relevant — așteaptă cel puțin 1-2 minute de la pornirea senzorului
înainte de a testa acest endpoint).

### Pasul 10 — Oprirea aplicației

Când termini o sesiune de lucru:

1. În terminalul cu senzorul virtual, apasă `Ctrl+C`.
2. În terminalul cu `docker compose up`, apasă `Ctrl+C` — asta oprește
   containerele (datele rămân salvate, în volume Docker).

Data viitoare, ca să reiei lucrul, e suficient:

```bash
docker compose up
```

(fără `--build`, decât dacă ai modificat codul din `backend/`) și, separat,
`python virtual_sensor.py` din folderul `sensor/`.

---

## 7. Depanare — probleme frecvente și soluții

Aceste probleme au apărut real în timpul dezvoltării proiectului și merită
documentate — sunt utile atât pentru tine, cât și ca material pentru
capitolul de testare/implementare al disertației.

### "WSL2 is unable to start since virtualization is not enabled"

Apare la `docker compose up`, de obicei ca eroare `500 Internal Server
Error` la tragerea unei imagini. Cauza: componentele Windows necesare
WSL2 nu sunt activate.

**Verificare rapidă:** Task Manager → tab Performance → CPU → linia
"Virtualization" trebuie să scrie `Enabled`.

- Dacă scrie `Disabled`: virtualizarea hardware (Intel VT-x / AMD-V)
  trebuie activată din BIOS/UEFI (repornești PC-ul, intri în BIOS, cauți
  opțiunea "Virtualization Technology" sau "SVM Mode").
- Dacă scrie `Enabled` (cazul cel mai frecvent): lipsesc componentele
  Windows. Rulează, ca Administrator:

  ```bash
  wsl --install --no-distribution
  ```

  apoi **repornește PC-ul**.

### `curl` în PowerShell cere confirmare / afișează un avertisment de securitate

În PowerShell, `curl` este de fapt un alias pentru `Invoke-WebRequest`, care
încearcă să parseze pagina ca HTML. Soluție: folosește `curl.exe` explicit
(binarul real de curl, inclus în Windows 10/11) în loc de `curl`:

```bash
curl.exe http://localhost:8000/health
```

### `pip: command not found` / `python: command not found`

Windows are un "stub" din Microsoft Store care se activează când scrii
`python` fără să ai Python instalat real — dă o eroare confuză
("install from the Microsoft Store"). Soluție: instalează Python real
(`winget install Python.Python.3.12`) și **redeschide terminalul**.

### Dashboard-ul Grafana arată "No data" pe toate panourile

De obicei, unul din aceste trei cazuri:

1. **Senzorul nu rulează** — verifică `curl.exe http://localhost:8000/latest`;
   dacă arată `no_data`, senzorul nu a trimis nimic încă.
2. **Datasource-ul InfluxDB din Grafana nu are UID-ul corect** — dacă ai
   editat manual `grafana/provisioning/datasources/influxdb.yaml` și ai
   schimbat `uid`, Grafana poate rămâne cu o referință internă coruptă la
   vechiul UID. Soluție (sigură, nu pierde date din InfluxDB — doar
   configurările interne ale Grafana):

   ```bash
   docker compose rm -sf grafana
   docker volume rm water-filter-monitor_grafana-data
   docker compose up -d grafana
   ```

3. **Intervalul de timp selectat în Grafana** (dreapta-sus, "Last 6 hours")
   nu acoperă momentul în care au fost scrise datele — extinde intervalul.

### Containerul `grafana` apare "Exited" în `docker compose ps`

Vezi eroarea exactă cu:

```bash
docker compose logs grafana --tail 50
```

Dacă vezi `Datasource provisioning error: data source not found`, aplică
soluția de la punctul 2 de mai sus.

---

## 8. Argumentarea alegerilor tehnice (pentru disertație)

- **De ce senzor virtual, nu hardware real?** Permite control complet asupra
  scenariilor de degradare (rate diferite, condiții de rețea variate),
  reproductibilitate perfectă între rulări, și accelerare temporală —
  imposibil de obținut cu un filtru fizic real într-un interval de timp
  rezonabil pentru o disertație.
- **De ce MQTT, nu HTTP direct de la senzor?** MQTT este protocolul
  standard de facto în IoT — publish/subscribe, overhead minim, potrivit
  pentru dispozitive cu resurse și lățime de bandă limitate (relevant mai
  ales în contextul comparației cu latențele de rețea 5G/4G simulate).
- **De ce InfluxDB, nu o bază de date relațională (ex. PostgreSQL)?**
  Datele sunt strict serii de timp cu frecvență ridicată de scriere;
  InfluxDB oferă compresie, politici de retenție și interogări Flux
  optimizate special pentru acest tipar de acces, spre deosebire de o bază
  relațională generică.
- **De ce regresie liniară pe logaritm, nu o rețea neuronală, pentru
  predicție?** Modelul fizic de degradare a filtrului este explicit
  exponențial; liniarizarea prin logaritm oferă un predictor simplu,
  rapid, interpretabil (raportează panta și `R²`) — potrivit pentru o
  demonstrație riguroasă și ușor de apărat la susținere, cu o direcție
  clară de extindere ca "lucru viitor" (ex. regresie polinomială, LSTM,
  pentru scenarii de degradare neliniare).
- **De ce Docker Compose pentru infrastructură, dar Python nativ pentru
  senzor?** Componentele de infrastructură (broker, bază de date, backend,
  dashboard) beneficiază de izolare, reproductibilitate și pornire cu o
  singură comandă. Senzorul, fiind componenta cel mai des modificată în
  timpul dezvoltării (ajustarea modelului de degradare, testarea de
  scenarii), rulează nativ pentru iterație rapidă, fără reconstruire de
  imagini Docker la fiecare modificare.

---

## 9. Fișă rapidă de comenzi

```bash
# Pornire completă (prima dată sau după modificări de cod)
docker compose up --build

# Pornire (rulările ulterioare, fără rebuild)
docker compose up

# Pornire în fundal (fără să blocheze terminalul)
docker compose up -d

# Status containere
docker compose ps

# Log-uri ale unui serviciu anume
docker compose logs backend --tail 50
docker compose logs grafana --tail 50

# Restart un singur serviciu
docker compose restart grafana

# Oprire (păstrează datele)
docker compose stop
# sau, din terminalul atașat: Ctrl+C

# Pornire senzor virtual
cd sensor
python virtual_sensor.py

# Verificări rapide
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/latest
curl.exe http://localhost:8000/history?hours=1
curl.exe http://localhost:8000/predict

# Interfețe web
# Grafana:   http://localhost:3000   (admin / admin)
# InfluxDB:  http://localhost:8086   (admin / admin12345)
# Backend:   http://localhost:8000
```
