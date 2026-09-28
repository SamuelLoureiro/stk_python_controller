#if defined(ARDUINO_UNOR4_WIFI)
  #include <WiFiS3.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
#else
  #include <WiFi.h>
#endif

#include <WiFiUdp.h>

// Controleur de drift Wi-Fi (UDP) pour SuperTuxKart

// Parametres reseau
const char* ssid     = "Rew is gay";
const char* password = "samishot";

// IP du PC qui execute serveur.py / STK
IPAddress serverIP(172, 16, 11, 223); 
const unsigned int serverPort = 6006;
const unsigned int localPort  = 6006;

WiFiUDP udp;

// Broches du capteur
const int TOUCH_PIN = A0;           // Capteur tactile Grove
const int TOUCH_PIN_SECONDARY = A1; // Broche secondaire optionnelle
const int LED_PIN = LED_BUILTIN;

const bool USE_PIN_A1 = false;
const unsigned long DEBOUNCE_MS = 50; // Filtre anti-rebond (50ms)

int lastReading = LOW;
int stableState = LOW;
unsigned long lastDebounceTime = 0;

void sendUdpCommand(const char* command) {
  udp.beginPacket(serverIP, serverPort);
  udp.write(command);
  udp.endPacket();
  Serial.print("Sent UDP: ");
  Serial.println(command);
}

// Envoi repete pour eviter les pertes de paquets UDP en relachant le drift
void sendReleaseCommand() {
  for (int i = 0; i < 3; i++) {
    udp.beginPacket(serverIP, serverPort);
    udp.write("R_SKIDDING");
    udp.endPacket();
    delay(10);
  }
  Serial.println("Sent UDP: R_SKIDDING (with redundancy)");
}

void setup() {
  Serial.begin(115200);

  pinMode(TOUCH_PIN, INPUT);
  if (USE_PIN_A1) {
    pinMode(TOUCH_PIN_SECONDARY, INPUT);
  }

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  delay(1000);

  #if defined(ARDUINO_UNOR4_WIFI)
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("ERROR: Arduino UNO R4 Wi-Fi module did not respond!");
    Serial.println("-> Disconnect USB cable from PC for 5 seconds and reconnect.");
    while (true) {
      digitalWrite(LED_PIN, HIGH);
      delay(100);
      digitalWrite(LED_PIN, LOW);
      delay(100);
    }
  }
  #endif

  WiFi.disconnect();
  delay(1000);

  Serial.println();
  Serial.print("Connecting to network: ");
  Serial.println(ssid);

  int attempt = 1;
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("Attempt #");
    Serial.print(attempt++);
    Serial.print(" connecting");

    WiFi.begin(ssid, password);

    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt < 10000)) {
      delay(500);
      Serial.print(".");
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }
    Serial.println();

    if (WiFi.status() != WL_CONNECTED) {
      int st = WiFi.status();
      Serial.print("Still not connected. Status code: ");
      Serial.print(st);
      if (st == WL_NO_SSID_AVAIL) {
        Serial.println(" (Network not found! Check range and 2.4 GHz frequency)");
      } else if (st == WL_CONNECT_FAILED) {
        Serial.println(" (Authentication failed! Check password)");
      } else {
        Serial.println(" (Waiting for router response...)");
      }
      delay(1500);
    }
  }

  digitalWrite(LED_PIN, LOW);
  Serial.println("\n>>> Wi-Fi Connected Successfully! <<<");
  Serial.print("Arduino IP: ");
  Serial.println(WiFi.localIP());

  udp.begin(localPort);
  Serial.println("Ready! Touch the sensor to trigger Drift.");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected! Reconnecting...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    delay(2000);
    return;
  }

  int currentReading = digitalRead(TOUCH_PIN);

  if (USE_PIN_A1 && digitalRead(TOUCH_PIN_SECONDARY) == HIGH) {
    currentReading = HIGH;
  }

  if (currentReading != lastReading) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
    if (currentReading != stableState) {
      stableState = currentReading;

      if (stableState == HIGH) {
        sendUdpCommand("P_SKIDDING");
        digitalWrite(LED_PIN, HIGH);
      } else {
        sendReleaseCommand();
        digitalWrite(LED_PIN, LOW);
      }
    }
  }

  lastReading = currentReading;
}
