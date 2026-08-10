# network_sim

`latency_output.csv` conține în prezent valori de exemplu (placeholder),
doar ca să existe un fișier valid pe care `virtual_sensor.py` să-l poată citi
dacă `network.use_latency_file: true` în `sensor/config.yaml`.

## Cum obții date reale din ns-3 / Simu5G (rulat separat, în WSL2)

1. Instalează ns-3 (+ modulul Simu5G, dacă vrei stack 5G NR) în WSL2.
2. Configurează un scenariu cu N noduri IoT care trimit pachete periodic
   către o stație de bază / gNB, în `ns3_config/` (script `.cc` sau `.py`).
3. La finalul simulării, exportă latențele per-pachet într-un CSV cu
   exact acest format (header inclus):

   ```
   packet_id,latency_ms
   1,12.4
   2,14.1
   ...
   ```

4. Suprascrie `latency_output.csv` cu rezultatele reale.
5. În `sensor/config.yaml`, setează `network.use_latency_file: true` —
   senzorul virtual va aplica automat aceste latențe ca delay înainte de
   fiecare `publish()` MQTT, simulând efectul rețelei asupra timpului de
   livrare a datelor.

Acest fișier fiind separat de restul stack-ului Docker, poți rula simulările
ns-3 oricând, independent, și doar copia CSV-ul rezultat aici.
