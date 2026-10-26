/*
 * QuSec ESP32 Firmware
 * -------------------
 * Firmware for the 4 ESP32 nodes in the QuSec Quantum Security Architecture:
 * 1. Sender (Alice)
 * 2. Receiver (Bob)
 * 3. Attacker (Eve)
 * 4. Auditor (QAuditor)
 *
 * Responsibilities:
 * - True Random Number Generation (TRNG) using esp_random() hardware entropy
 * - Classical Channel Wireless Relay (Wi-Fi UDP / ESP-NOW) between Sender & Receiver
 * - USB-Serial command interface with QuSec Python driver (115200 baud)
 * - Link heartbeat ping-pong
 *
 * Flash using Arduino IDE or PlatformIO:
 * Board: "ESP32 Dev Module"
 * Upload Speed: 115200 or 921600
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_system.h>

// Default configuration
#define FIRMWARE_VERSION "1.2.0"
#define BAUD_RATE 115200
#define UDP_PORT 9877

// Set device role: "ALICE", "BOB", "ATTACKER", "AUDITOR"
String deviceRole = "ALICE";

// Wi-Fi Access Point / Station configuration for direct wireless link
const char* AP_SSID = "QuSec_ESP32_QuantumNet";
const char* AP_PASS = "QuantumSecure2026!";

WiFiUDP udp;
IPAddress peerIP(192, 168, 4, 2); // Default Bob IP on AP network

void setup() {
  Serial.begin(BAUD_RATE);
  delay(500);

  // Configure Wi-Fi mode
  if (deviceRole == "ALICE") {
    // Alice sets up SoftAP
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
  } else {
    // Bob / Attacker / Auditor connects to SoftAP
    WiFi.mode(WIFI_STA);
    WiFi.begin(AP_SSID, AP_PASS);
  }

  udp.begin(UDP_PORT);
  Serial.println("{\"status\":\"READY\",\"firmware\":\"" FIRMWARE_VERSION "\",\"role\":\"" + deviceRole + "\"}");
}

void loop() {
  // 1. Process serial commands from Laptop QuSec driver
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleSerialCommand(cmd);
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
    }
  }
}

void handleSerialCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("{\"status\":\"PONG\",\"role\":\"" + deviceRole + "\",\"fw\":\"" FIRMWARE_VERSION "\"}");
  }
  else if (cmd.startsWith("RNG")) {
    // Request hardware random bytes: "RNG <bytes>"
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
    // Transmit classical packet wirelessly: "TX <hex_data>"
    String data = cmd.substring(3);
    udp.beginPacket(peerIP, UDP_PORT);
    udp.print(data);
    udp.endPacket();
    Serial.println("{\"status\":\"OK\",\"tx_bytes\":" + String(data.length()) + "}");
  }
  else if (cmd.startsWith("SET_ROLE ")) {
    deviceRole = cmd.substring(9);
    deviceRole.trim();
    deviceRole.toUpperCase();
    Serial.println("{\"status\":\"OK\",\"role\":\"" + deviceRole + "\"}");
  }
  else if (cmd == "STATUS") {
    Serial.println("{\"status\":\"ONLINE\",\"role\":\"" + deviceRole + "\",\"ip\":\"" + WiFi.localIP().toString() + "\"}");
  }
  else {
    Serial.println("{\"status\":\"ERR\",\"msg\":\"Unknown command\"}");
  }
}
