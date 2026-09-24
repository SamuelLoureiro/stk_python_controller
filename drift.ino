#if defined(ARDUINO_UNOR4_WIFI)
  #include <WiFiS3.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
#else
  // Default for ESP32 and other boards with WiFi support
  #include <WiFi.h>
#endif

#include <WiFiUdp.h>

/**
 * Project: Drift Controller via Wi-Fi (UDP) for SuperTuxKart
 * Compatible boards: Arduino UNO R4 WiFi, ESP32, ESP8266
 */

// ================= Network Settings =================
const char* ssid     = "Rew is gay";         // Network SSID (2.4 GHz)
const char* password = "samishot";       // Network password

// IP address of computer running STK_input_server_v2.py
IPAddress serverIP(172, 16, 11, 223); 
const unsigned int serverPort = 6006;           // Python server port
const unsigned int localPort  = 6006;           // Arduino local port

// UDP client instance
WiFiUDP udp;

// ================= Pin Configuration =================
const int TOUCH_PIN = A0;           // Primary Grove touch sensor read pin
const int TOUCH_PIN_SECONDARY = A1; // Secondary pin (if using 2-channel touch sensor)
const int LED_PIN = LED_BUILTIN;    // Onboard LED for visual feedback

// Settings
const bool USE_PIN_A1 = false;       // 'true' only if using a second button on A1
const unsigned long DEBOUNCE_MS = 50; // Sensor debounce stabilization time (50ms)

// State control variables
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

// Send release 3 times to ensure 100% delivery and avoid stuck drift
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

  // Configure sensor pins as input
  pinMode(TOUCH_PIN, INPUT);
  if (USE_PIN_A1) {
    pinMode(TOUCH_PIN_SECONDARY, INPUT);
  }

  // Configure onboard LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Wait 1 second for serial port to stabilize
  delay(1000);

  #if defined(ARDUINO_UNOR4_WIFI)
  // Check if UNO R4 WiFi module is responding
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

  // Clear any previously stuck connection
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

    // Wait up to 10 seconds to receive IP via DHCP without aborting
    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startAttempt < 10000)) {
      delay(500);
      Serial.print(".");
      digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blink LED while attempting
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

  // Initialize UDP socket
  udp.begin(localPort);
  Serial.println("Ready! Touch the sensor to trigger Drift.");
}

void loop() {
  // If Wi-Fi disconnects, attempt reconnect
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected! Reconnecting...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    delay(2000);
    return;
  }

  // Read primary sensor (A0)
  int currentReading = digitalRead(TOUCH_PIN);

  // If secondary pin is enabled, consider touched if either is HIGH
  if (USE_PIN_A1 && digitalRead(TOUCH_PIN_SECONDARY) == HIGH) {
    currentReading = HIGH;
  }

  // Debounce filter
  if (currentReading != lastReading) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
    // If signal stabilized and changed state
    if (currentReading != stableState) {
      stableState = currentReading;

      if (stableState == HIGH) {
        // Sensor touched -> Activate drift
        sendUdpCommand("P_SKIDDING");
        digitalWrite(LED_PIN, HIGH);
      } else {
        // Sensor released -> Release drift with guaranteed redundancy
        sendReleaseCommand();
        digitalWrite(LED_PIN, LOW);
      }
    }
  }

  lastReading = currentReading;
}
