/*
 * QuSec Universal ESP32 Firmware
 * ------------------------------
 * Universal firmware for ALL ESP32 nodes in the QuSec Quantum Security Architecture:
 * - Sender ESP32
 * - Receiver ESP32
 * - Attacker (Eve)
 * - Auditor (QAuditor)
 *
 * NOTE: Both Sender and Receiver ESP32 boards use THIS EXACT SAME CODE!
 * The role (SENDER / RECEIVER) is automatically configured by QuSec over USB Serial,
 * or defaults to SENDER on the Access Point host and RECEIVER on the station client.
 *
 * Hardware LEDs:
 * - Pin 2 (GPIO 2): Primary Status LED (Built-in onboard blue LED). Solid when ready.
 * - Pin 4 (GPIO 4): SECOND LED - Security Threat Alarm LED.
 *                   Blinks rapidly whenever a quantum threat (QBER > 6%, CHSH <= 2.0,
 *                   forgery, or tampering) is detected!
 *
 * Responsibilities:
 * - Hardware True Random Number Generation (TRNG) via esp_random()
 * - Classical Channel Wireless Relay (Wi-Fi UDP) for Pauli correction bits & MAC tags
 * - Hardware Security Alarm LED controller (Blinks on threat detection)
 * - USB-Serial command interface with QuSec Python driver (115200 baud)
 *
 * Uploading to ESP32:
 * 1. Open this file in Arduino IDE.
 * 2. Select Board: "ESP32 Dev Module" (or your specific ESP32 board).
 * 3. Upload to BOTH ESP32 boards!
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_system.h>

#define FIRMWARE_VERSION "2.0.0"
#define BAUD_RATE 115200
#define UDP_PORT 9877

// Hardware Pin Assignments
#define LED_STATUS_PIN 2   // Primary status LED (GPIO 2 onboard)
#define LED_ALARM_PIN  4   // SECOND LED: Security Threat Alarm (GPIO 4)

// Device Role: "SENDER" (hosts SoftAP) or "RECEIVER" (connects to SoftAP)
String deviceRole = "SENDER";

// Wi-Fi Access Point / Station parameters
const char* AP_SSID = "QuSec_ESP32_QuantumNet";
const char* AP_PASS = "QuantumSecure2026!";

WiFiUDP udp;
IPAddress peerIP(192, 168, 4, 2); // Default peer IP on AP subnet

// Non-blocking Alarm LED State
bool alarmActive = false;
unsigned long lastAlarmBlink = 0;
int alarmBlinkInterval = 150; // 150ms fast blink on threat
bool alarmLedState = false;

void initWiFi() {
  WiFi.disconnect(true);
  delay(100);

  if (deviceRole == "SENDER" || deviceRole == "ALICE") {
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(AP_SSID, AP_PASS);
    peerIP = IPAddress(192, 168, 4, 2);
  } else {
    WiFi.mode(WIFI_STA);
    WiFi.begin(AP_SSID, AP_PASS);
    peerIP = IPAddress(192, 168, 4, 1);
  }

  udp.begin(UDP_PORT);
}

void setup() {
  Serial.begin(BAUD_RATE);
  delay(300);

  pinMode(LED_STATUS_PIN, OUTPUT);
  pinMode(LED_ALARM_PIN, OUTPUT);
  digitalWrite(LED_STATUS_PIN, HIGH); // Status ON
  digitalWrite(LED_ALARM_PIN, LOW);   // Alarm OFF initially

  initWiFi();

  Serial.println("{\"status\":\"READY\",\"firmware\":\"" FIRMWARE_VERSION "\",\"role\":\"" + deviceRole + "\",\"alarm_pin\":4}");
}

void loop() {
  // 1. Process serial commands from Laptop QuSec driver
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      handleSerialCommand(cmd);
    }
  }

  // 2. Process incoming wireless classical packets
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char packetBuffer[2048];
    int len = udp.read(packetBuffer, 2047);
    if (len > 0) {
      packetBuffer[len] = 0;
      // Forward wireless packet to Laptop via Serial
      Serial.print("RX ");
      Serial.println(packetBuffer);

      // Brief flash on status LED for wireless activity
      digitalWrite(LED_STATUS_PIN, LOW);
      delay(5);
      digitalWrite(LED_STATUS_PIN, HIGH);
    }
  }

  // 3. Non-blocking Blinking of Second LED if Threat Alarm is Active
  if (alarmActive) {
    unsigned long now = millis();
    if (now - lastAlarmBlink >= (unsigned long)alarmBlinkInterval) {
      lastAlarmBlink = now;
      alarmLedState = !alarmLedState;
      digitalWrite(LED_ALARM_PIN, alarmLedState ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_ALARM_PIN, LOW);
  }
}

void handleSerialCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("{\"status\":\"PONG\",\"role\":\"" + deviceRole + "\",\"alarm\":" + (alarmActive ? "true" : "false") + ",\"fw\":\"" FIRMWARE_VERSION "\"}");
  }
  else if (cmd.startsWith("ALARM ") || cmd.startsWith("THREAT ") || cmd.startsWith("ALERT ")) {
    // "ALARM 1 [ms]" (enable blinking) or "ALARM 0" (clear)
    int spaceIdx = cmd.indexOf(' ');
    String arg = cmd.substring(spaceIdx + 1);
    arg.trim();

    if (arg.startsWith("1") || arg.startsWith("true") || arg.startsWith("ON")) {
      alarmActive = true;
      int subSpace = arg.indexOf(' ');
      if (subSpace > 0) {
        int customInterval = arg.substring(subSpace + 1).toInt();
        if (customInterval >= 50 && customInterval <= 2000) {
          alarmBlinkInterval = customInterval;
        }
      } else {
        alarmBlinkInterval = 150; // default 150ms rapid alert
      }
      Serial.println("{\"status\":\"OK\",\"alarm\":\"ACTIVE\",\"pin\":4,\"blink_ms\":" + String(alarmBlinkInterval) + "}");
    } else {
      alarmActive = false;
      alarmLedState = false;
      digitalWrite(LED_ALARM_PIN, LOW);
      Serial.println("{\"status\":\"OK\",\"alarm\":\"CLEARED\",\"pin\":4}");
    }
  }
  else if (cmd.startsWith("RNG")) {
    // Hardware TRNG request: "RNG <bytes>"
    int numBytes = 16;
    int spaceIdx = cmd.indexOf(' ');
    if (spaceIdx > 0) {
      numBytes = cmd.substring(spaceIdx + 1).toInt();
      if (numBytes <= 0 || numBytes > 256) numBytes = 16;
    }

    String hexOut = "";
    for (int i = 0; i < numBytes; i++) {
      uint8_t r = (uint8_t)(esp_random() & 0xFF);
      char buf[3];
      sprintf(buf, "%02x", r);
      hexOut += buf;
    }
    Serial.println("{\"status\":\"OK\",\"hex\":\"" + hexOut + "\",\"bytes\":" + String(numBytes) + "}");
  }
  else if (cmd.startsWith("TX ")) {
    // Transmit classical packet wirelessly: "TX <data>"
    String data = cmd.substring(3);
    udp.beginPacket(peerIP, UDP_PORT);
    udp.print(data);
    udp.endPacket();
    Serial.println("{\"status\":\"OK\",\"tx_bytes\":" + String(data.length()) + "}");
  }
  else if (cmd.startsWith("SET_ROLE ")) {
    String newRole = cmd.substring(9);
    newRole.trim();
    newRole.toUpperCase();
    if (newRole != deviceRole) {
      deviceRole = newRole;
      initWiFi();
    }
    Serial.println("{\"status\":\"OK\",\"role\":\"" + deviceRole + "\"}");
  }
  else if (cmd == "STATUS") {
    Serial.println("{\"status\":\"ONLINE\",\"role\":\"" + deviceRole + "\",\"ip\":\"" + WiFi.localIP().toString() + "\",\"alarm\":" + (alarmActive ? "true" : "false") + "}");
  }
  else {
    Serial.println("{\"status\":\"ERR\",\"msg\":\"Unknown command\"}");
  }
}
