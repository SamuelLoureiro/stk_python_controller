/*
 * Boitier du sourd -- Arduino UNO R4 WiFi + Grove Base Shield V2.
 * NON TESTE SUR LA CARTE (le cote PC l'est).
 *
 *   D2  Touch Sensor         doigt pose   -> accelerer
 *   A0  Piezo Vibration      une tape     -> lancer l'objet
 *   D4  Ultrasonic Ranger    pied proche  -> freiner (seuil FREIN_CM cote PC)
 *
 * Toutes les 50 ms, en UDP vers le PC (port 6010) : touche=1 dist=23 tapes=12 piezo=412
 * piezo = maximum lu sur la periode, pour regler SEUIL_PIEZO.
 */

#include <WiFiS3.h>
#include <WiFiUdp.h>

// ======================= A REMPLIR =======================
const char* WIFI_NOM = "A_REMPLIR";          // reseau 2,4 GHz
const char* WIFI_MDP = "A_REMPLIR";

// IP du PC, affichee par trio.py (elle change avec le reseau)
IPAddress IP_PC(192, 168, 1, 10);
const unsigned int PORT_PC = 6010;
// =========================================================

const int BROCHE_TOUCHE = 2;
const int BROCHE_PIEZO = A0;
const int BROCHE_ULTRASON = 4;
const bool AVEC_ULTRASON = true;             // false si le capteur n'est pas branche

const int SEUIL_PIEZO = 300;                 // 0..1023 ; a regler en lisant piezo=
const unsigned long REFRACTAIRE_MS = 150;    // une tape vibre plusieurs ms : un seul coup
const unsigned long PERIODE_ENVOI_MS = 50;
const unsigned long PERIODE_ULTRASON_MS = 100;
// 6 ms ~ 1 m. Court expres : pendant pulseIn, le piezo n'est pas lu.
const unsigned long ATTENTE_ECHO_US = 6000;

WiFiUDP udp;
unsigned long tapes = 0;
unsigned long derniere_tape = 0;
bool piezo_haut = false;
int piezo_max = 0;
long distance_cm = -1;
unsigned long dernier_envoi = 0;
unsigned long derniere_mesure = 0;

// Une seule broche : emettre, puis ecouter.
long mesurer_distance() {
  pinMode(BROCHE_ULTRASON, OUTPUT);
  digitalWrite(BROCHE_ULTRASON, LOW);
  delayMicroseconds(2);
  digitalWrite(BROCHE_ULTRASON, HIGH);
  delayMicroseconds(5);
  digitalWrite(BROCHE_ULTRASON, LOW);
  pinMode(BROCHE_ULTRASON, INPUT);
  unsigned long duree = pulseIn(BROCHE_ULTRASON, HIGH, ATTENTE_ECHO_US);
  if (duree == 0) {
    return -1;                               // pas d'echo : rien devant
  }
  return duree / 29 / 2;                     // aller-retour, ~29 us par cm
}

void connecter() {
  digitalWrite(LED_BUILTIN, LOW);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Connexion a ");
    Serial.println(WIFI_NOM);
    WiFi.begin(WIFI_NOM, WIFI_MDP);
    unsigned long debut = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - debut < 10000) {
      delay(250);
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }
  }
  digitalWrite(LED_BUILTIN, HIGH);           // LED allumee = connecte
  Serial.print("Connecte, IP de la carte : ");
  Serial.println(WiFi.localIP());
  Serial.print("Envoi vers ");
  Serial.print(IP_PC);
  Serial.print(":");
  Serial.println(PORT_PC);
}

void setup() {
  Serial.begin(115200);
  pinMode(BROCHE_TOUCHE, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  delay(1000);

  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("Module Wi-Fi muet : debrancher l'USB 5 secondes et rebrancher.");
    while (true) {
      digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
      delay(100);
    }
  }
  connecter();
  udp.begin(PORT_PC);
}

void loop() {
  unsigned long maintenant = millis();

  // Fronts montants + periode refractaire : une tape vibre plusieurs ms.
  int p = analogRead(BROCHE_PIEZO);
  if (p > piezo_max) {
    piezo_max = p;
  }
  if (p > SEUIL_PIEZO) {
    if (!piezo_haut && maintenant - derniere_tape > REFRACTAIRE_MS) {
      tapes++;
      derniere_tape = maintenant;
    }
    piezo_haut = true;
  } else {
    piezo_haut = false;
  }

  if (AVEC_ULTRASON && maintenant - derniere_mesure >= PERIODE_ULTRASON_MS) {
    derniere_mesure = maintenant;
    distance_cm = mesurer_distance();
  }

  if (maintenant - dernier_envoi >= PERIODE_ENVOI_MS) {
    dernier_envoi = maintenant;
    if (WiFi.status() != WL_CONNECTED) {
      connecter();                           // le PC relache tout pendant ce temps
      return;
    }
    char paquet[80];
    snprintf(paquet, sizeof(paquet), "touche=%d dist=%ld tapes=%lu piezo=%d",
             digitalRead(BROCHE_TOUCHE) == HIGH ? 1 : 0,
             distance_cm, tapes, piezo_max);
    udp.beginPacket(IP_PC, PORT_PC);
    udp.write((const uint8_t*)paquet, strlen(paquet));
    udp.endPacket();
    piezo_max = 0;

    // Moniteur serie (115200 bauds) : une ligne par seconde
    static unsigned long derniere_trace = 0;
    if (maintenant - derniere_trace >= 1000) {
      derniere_trace = maintenant;
      Serial.println(paquet);
    }
  }
}
