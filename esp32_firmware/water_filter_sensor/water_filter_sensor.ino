/*
 * Firmware ESP32 pentru senzorul fizic al filtrului de apa.
 *
 * Citeste 2 senzori de presiune (inainte/dupa filtru) si un debitmetru cu
 * impulsuri, calculeaza aceleasi campuri pe care le publica senzorul virtual
 * (sensor/main.py), si le trimite prin MQTT catre acelasi topic pe care
 * backend-ul FastAPI il asculta deja - deci NU e nevoie de nicio schimbare
 * in backend, doar schimbi sursa datelor.
 *
 * Librarii necesare (Arduino Library Manager):
 *   - PubSubClient (Nick O'Leary)
 *   - ArduinoJson  (Benoit Blanchon), v6 sau v7
 *
 * Hardware:
 *   - ESP32 DevKit (orice varianta cu WiFi)
 *   - 2x senzor de presiune analogic 0.5-4.5V (inainte/dupa filtru), FIECARE
 *     printr-un divizor de tensiune (vezi nota de mai jos - OBLIGATORIU,
 *     altfel arzi pinul ADC al ESP32)
 *   - 1x debitmetru cu impulsuri (YF-S201 sau similar)
 *
 * ATENTIE HARDWARE: ESP32 citeste analogic doar 0-3.3V. Senzorii de presiune
 * ieftini dau 0.5-4.5V. Foloseste un divizor rezistiv (ex. R1=10k spre
 * semnal, R2=15k spre GND, iesirea intre ele spre ADC) ca sa nu depasesti
 * 3.3V - altfel deteriorezi pinul ADC definitiv.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "time.h"

// ---------------------------------------------------------------------
// Configurare - editeaza aceste valori. Pentru un proiect real, muta-le
// intr-un config.h separat si adauga-l in .gitignore, la fel cum am facut
// cu .env.secrets in backend - nu urca parola de WiFi pe GitHub.
// ---------------------------------------------------------------------
const char* WIFI_SSID = "numele-retelei-wifi";
const char* WIFI_PASSWORD = "parola-wifi";

// Varianta LOCALA (pas 1, cel mai simplu de testat): broker-ul Mosquitto
// care ruleaza deja in docker-compose, pe IP-ul local al PC-ului tau (NU
// "localhost" - ESP32 e alt dispozitiv in retea). Afla-l cu "ipconfig".
const char* MQTT_HOST = "192.168.1.100";  // <-- IP-ul PC-ului tau in retea
const int MQTT_PORT = 1883;
const char* MQTT_USER = "";  // gol daca Mosquitto nu are autentificare
const char* MQTT_PASSWORD = "";

// Varianta CLOUD (pas 2, acces de oriunde): decomenteaza si foloseste
// WiFiClientSecure in loc de WiFiClient mai jos, plus:
//   const char* MQTT_HOST = "xxxxxxx.s1.eu.hivemq.cloud";
//   const int MQTT_PORT = 8883;  // TLS
//   MQTT_USER / MQTT_PASSWORD = credentialele contului HiveMQ Cloud

const char* MQTT_TOPIC = "home/water/filter";
const char* DEVICE_ID = "esp32-filtru-01";

const unsigned long PUBLISH_INTERVAL_MS = 5000;  // acelasi interval ca senzorul virtual

// ---------------------------------------------------------------------
// Pini hardware
// ---------------------------------------------------------------------
const int PIN_PRESIUNE_INAINTE = 34;  // ADC1_CH6 - senzor P1, inainte de filtru
const int PIN_PRESIUNE_DUPA = 35;     // ADC1_CH7 - senzor P2, dupa filtru
const int PIN_DEBITMETRU = 27;        // GPIO cu intrerupere, pentru YF-S201

// ---------------------------------------------------------------------
// Calibrare senzori - AJUSTEAZA dupa datasheet-ul exact al senzorilor tai
// ---------------------------------------------------------------------
const float ADC_VREF = 3.3;
const int ADC_MAX = 4095;              // ESP32: ADC pe 12 biti
const float DIVIZOR_RAPORT = 0.6;      // raportul divizorului rezistiv (vezi nota hardware)
const float SENZOR_V_MIN = 0.5;        // tensiunea senzorului la 0 presiune
const float SENZOR_V_MAX = 4.5;        // tensiunea senzorului la presiune maxima
const float SENZOR_PRESIUNE_MAX_BAR = 12.0;  // presiunea maxima a senzorului (bar)

const float DEBITMETRU_PULSURI_PE_LITRU_MIN = 7.5;  // YF-S201: Hz = 7.5 * L/min

// ---------------------------------------------------------------------
// Stare globala
// ---------------------------------------------------------------------
WiFiClient espClient;
PubSubClient mqttClient(espClient);

volatile unsigned long numarPulsuri = 0;
unsigned long ultimaCitirePulsuri = 0;
unsigned long ultimaPublicare = 0;

void IRAM_ATTR onPulsDebitmetru() {
  numarPulsuri++;
}

// ---------------------------------------------------------------------
// Conversii senzor: ADC brut -> valoare fizica
// ---------------------------------------------------------------------
float citestePresiuneBar(int pin) {
  int raw = analogRead(pin);
  float vAdc = (raw / (float)ADC_MAX) * ADC_VREF;
  float vSenzor = vAdc / DIVIZOR_RAPORT;
  float fractie = (vSenzor - SENZOR_V_MIN) / (SENZOR_V_MAX - SENZOR_V_MIN);
  if (fractie < 0) fractie = 0;
  float presiuneBar = fractie * SENZOR_PRESIUNE_MAX_BAR;
  return presiuneBar;
}

float citesteDebitLmin() {
  noInterrupts();
  unsigned long pulsuri = numarPulsuri;
  numarPulsuri = 0;
  interrupts();

  unsigned long acum = millis();
  float secundeScurse = (acum - ultimaCitirePulsuri) / 1000.0;
  ultimaCitirePulsuri = acum;
  if (secundeScurse <= 0) return 0;

  float frecventaHz = pulsuri / secundeScurse;
  return frecventaHz / DEBITMETRU_PULSURI_PE_LITRU_MIN;
}

// ---------------------------------------------------------------------
// Conectivitate
// ---------------------------------------------------------------------
void conecteazaWiFi() {
  Serial.printf("[wifi] Conectare la %s...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[wifi] Conectat, IP local: %s\n", WiFi.localIP().toString().c_str());

  // NTP - avem nevoie de timp real pentru campul "timestamp", la fel ca
  // senzorul virtual (time.time() in Python)
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("[ntp] Sincronizare timp");
  time_t acum = time(nullptr);
  while (acum < 100000) {
    delay(300);
    Serial.print(".");
    acum = time(nullptr);
  }
  Serial.println(" ok");
}

void reconecteazaMqtt() {
  while (!mqttClient.connected()) {
    Serial.print("[mqtt] Conectare la broker...");
    bool ok;
    if (strlen(MQTT_USER) > 0) {
      ok = mqttClient.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD);
    } else {
      ok = mqttClient.connect(DEVICE_ID);
    }
    if (ok) {
      Serial.println(" conectat");
    } else {
      Serial.printf(" esuat, rc=%d, reincerc in 3s\n", mqttClient.state());
      delay(3000);
    }
  }
}

void publicaCitire(float presiuneInainte, float presiuneDupa, float debitLmin) {
  float presiuneDiferentiala = presiuneInainte - presiuneDupa;
  if (presiuneDiferentiala < 0) presiuneDiferentiala = 0;

  StaticJsonDocument<256> doc;
  doc["timestamp"] = (double)time(nullptr);
  doc["pressure_drop_bar"] = presiuneDiferentiala;
  doc["flow_rate_lmin"] = debitLmin;
  // Fara senzor de turbiditate montat inca - se poate adauga ulterior
  // (ex. DFRobot SEN0189) fara sa schimbi restul firmware-ului.
  doc["turbidity_ntu"] = 0.0;

  char payload[256];
  size_t n = serializeJson(doc, payload);

  bool trimis = mqttClient.publish(MQTT_TOPIC, payload, n);
  Serial.printf("[mqtt] %s -> %s\n", trimis ? "trimis" : "ESUAT", payload);
}

// ---------------------------------------------------------------------
// Setup / loop
// ---------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  pinMode(PIN_DEBITMETRU, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_DEBITMETRU), onPulsDebitmetru, FALLING);

  conecteazaWiFi();
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);

  ultimaCitirePulsuri = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    conecteazaWiFi();
  }
  if (!mqttClient.connected()) {
    reconecteazaMqtt();
  }
  mqttClient.loop();

  unsigned long acum = millis();
  if (acum - ultimaPublicare >= PUBLISH_INTERVAL_MS) {
    ultimaPublicare = acum;

    float p1 = citestePresiuneBar(PIN_PRESIUNE_INAINTE);
    float p2 = citestePresiuneBar(PIN_PRESIUNE_DUPA);
    float debit = citesteDebitLmin();

    publicaCitire(p1, p2, debit);
  }
}
