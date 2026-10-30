/*
 * QuSec Dedicated Attacker ESP32 Firmware (Eve - Adversary Node)
 * ==============================================================
 * Specialized firmware for the 3rd ESP32 connected to the Attacker's Laptop.
 *
 * Responsibilities:
 * 1. Hardware True Random Number Generation (TRNG) via internal esp_random()
 *    thermal/RF phase jitter noise for genuine quantum state disturbance injection.
 * 2. Wireless Packet Sniffing & Injection (Wi-Fi Promiscuous / UDP raw mode).
 * 3. Hardware Attack Activity Strobe LED:
 *    - GPIO 2: Primary Status LED (Solid when connected, flashes on serial command).
 *    - GPIO 4: High-intensity Adversary Attack Blast Indicator LED (Strobes rapidly
 *              during active state disturbance, Pauli tampering, forgery, or jamming).
 * 4. High-speed USB-Serial command interface (115200 baud).
 * 5. Hardware RF & UDP Jamming Burst Engine.
 *
 * Hardware Pin Assignments:
 * - GPIO 2: Primary Status / Link LED (Onboard Blue LED)
 * - GPIO 4: Adversary Attack Blast Indicator LED
 *
 * Flashing Instructions:
 * 1. Open this file in Arduino IDE.
 * 2. Select Board: "ESP32 Dev Module" (or your specific ESP32 board).
 * 3. Connect the 3rd ESP32 (Attacker) via USB.
 * 4. Select the corresponding COM / /dev/ttyUSB port.
 * 5. Click Upload.
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_system.h>
#include <esp_wifi.h>

#define FIRMWARE_VERSION "2.5.0-ATTACKER"
#define BAUD_RATE 115200
#define DEFAULT_UDP_PORT 9877

// Hardware Pin Assignments
#define LED_STATUS_PIN 2   // Primary status LED (GPIO 2 onboard)
#define LED_ALARM_PIN  4   // Adversary Attack Blast LED (GPIO 4)

// Wi-Fi Configuration
const char* AP_SSID = "QuSec_ESP32_QuantumNet";
const char* AP_PASS = "QuantumSecure2026!";

WiFiUDP udp;
IPAddress targetIP(192, 168, 4, 2); // Default target is Bob (Receiver)
int targetPort = DEFAULT_UDP_PORT;

// Attack Alert LED State (Non-blocking)
bool attackLedActive = false;
unsigned long lastAttackBlink = 0;
int attackBlinkInterval = 100; // 100ms rapid strobe during attacks
bool attackLedLevel = false;

// Statistics
unsigned long packetsInjected = 0;
unsigned long trngBytesGenerated = 0;
bool snifferActive = false;

// Promiscuous Sniffer Callback
void wifiPromiscuousCallback(void* buf, wifi_promiscuous_pkt_type_t type) {
  if (!snifferActive) return;
  wifi_promiscuous_pkt_t* pkt = (wifi_promiscuous_pkt_t*)buf;
  int len = pkt->rx_ctrl.sig_len;
  if (len > 0 && len <= 128) {
    Serial.print("SNIFF ");
    Serial.print(len);
    Serial.print(" ");
    for (int i = 0; i < min(len, 32); i++) {
      char hexBuf[3];
      sprintf(hexBuf, "%02x", pkt->payload[i]);
      Serial.print(hexBuf);
    }
    Serial.println();
  }
}

void initAttackerWiFi() {
  WiFi.disconnect(true);
  delay(100);

  // Connect as Station to QuSec network to intercept and inject
  WiFi.mode(WIFI_STA);
  WiFi.begin(AP_SSID, AP_PASS);

  udp.begin(DEFAULT_UDP_PORT);
}

void setup() {
  Serial.begin(BAUD_RATE);
  delay(300);

  pinMode(LED_STATUS_PIN, OUTPUT);
  pinMode(LED_ALARM_PIN, OUTPUT);

  digitalWrite(LED_STATUS_PIN, HIGH); // Status ON
  digitalWrite(LED_ALARM_PIN, LOW);   // Attack LED OFF initially

  initAttackerWiFi();

  // Announce Attacker firmware ready
  Serial.println("{\"status\":\"READY\",\"firmware\":\"" FIRMWARE_VERSION "\",\"role\":\"ATTACKER\",\"attack_pin\":4,\"status_pin\":2}");
}

void loop() {
  // 1. Process serial commands from Laptop QuSec Attacker driver
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      handleAttackerCommand(cmd);
    }
  }

  // 2. Process incoming UDP packets on the classical channel
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char packetBuffer[2048];
    int len = udp.read(packetBuffer, 2047);
    if (len > 0) {
      packetBuffer[len] = 0;
      // Forward intercepted packet to Laptop via Serial
      Serial.print("RX ");
      Serial.println(packetBuffer);

      // Brief status blink
      digitalWrite(LED_STATUS_PIN, LOW);
      delay(4);
      digitalWrite(LED_STATUS_PIN, HIGH);
    }
  }

  // 3. Non-blocking Blinking of Attack LED (GPIO 4) during active threat bursts
  if (attackLedActive) {
    unsigned long now = millis();
    if (now - lastAttackBlink >= (unsigned long)attackBlinkInterval) {
      lastAttackBlink = now;
      attackLedLevel = !attackLedLevel;
      digitalWrite(LED_ALARM_PIN, attackLedLevel ? HIGH : LOW);
    }
  } else {
    digitalWrite(LED_ALARM_PIN, LOW);
  }
}

void handleAttackerCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("{\"status\":\"PONG\",\"role\":\"ATTACKER\",\"fw\":\"" FIRMWARE_VERSION "\",\"attack_led\":" + String(attackLedActive ? "true" : "false") + "}");
  }
  else if (cmd.startsWith("RNG")) {
    // Hardware True Random Number Generation: "RNG <bytes>"
    int numBytes = 32;
    int spaceIdx = cmd.indexOf(' ');
    if (spaceIdx > 0) {
      numBytes = cmd.substring(spaceIdx + 1).toInt();
      if (numBytes <= 0 || numBytes > 256) numBytes = 32;
    }

    String hexOut = "";
    for (int i = 0; i < numBytes; i++) {
      uint8_t r = (uint8_t)(esp_random() & 0xFF);
      char buf[3];
      sprintf(buf, "%02x", r);
      hexOut += buf;
    }
    trngBytesGenerated += numBytes;
    Serial.println("{\"status\":\"OK\",\"hex\":\"" + hexOut + "\",\"bytes\":" + String(numBytes) + "}");
  }
  else if (cmd.startsWith("ALARM ") || cmd.startsWith("ATTACK_LED ")) {
    // Control Attack LED (GPIO 4): "ALARM 1 [blink_ms]" or "ALARM 0"
    int spaceIdx = cmd.indexOf(' ');
    String arg = cmd.substring(spaceIdx + 1);
    arg.trim();

    if (arg.startsWith("1") || arg.startsWith("true") || arg.startsWith("ON")) {
      attackLedActive = true;
      int subSpace = arg.indexOf(' ');
      if (subSpace > 0) {
        int customInterval = arg.substring(subSpace + 1).toInt();
        if (customInterval >= 30 && customInterval <= 2000) {
          attackBlinkInterval = customInterval;
        }
      } else {
        attackBlinkInterval = 100;
      }
      Serial.println("{\"status\":\"OK\",\"attack_led\":\"ACTIVE\",\"pin\":4,\"blink_ms\":" + String(attackBlinkInterval) + "}");
    } else {
      attackLedActive = false;
      attackLedLevel = false;
      digitalWrite(LED_ALARM_PIN, LOW);
      Serial.println("{\"status\":\"OK\",\"attack_led\":\"CLEARED\",\"pin\":4}");
    }
  }
  else if (cmd.startsWith("TX ")) {
    // Transmit attack payload frame wirelessly: "TX <data>"
    String data = cmd.substring(3);
    udp.beginPacket(targetIP, targetPort);
    udp.print(data);
    udp.endPacket();
    packetsInjected++;
    Serial.println("{\"status\":\"OK\",\"tx_bytes\":" + String(data.length()) + ",\"total_injected\":" + String(packetsInjected) + "}");
  }
  else if (cmd.startsWith("JAM ")) {
    // Hardware TRNG Jamming Burst: "JAM <count> [delay_ms]"
    int count = 15;
    int delayMs = 10;
    int space1 = cmd.indexOf(' ');
    int space2 = cmd.indexOf(' ', space1 + 1);
    if (space1 > 0) {
      if (space2 > 0) {
        count = cmd.substring(space1 + 1, space2).toInt();
        delayMs = cmd.substring(space2 + 1).toInt();
      } else {
        count = cmd.substring(space1 + 1).toInt();
      }
    }
    count = constrain(count, 1, 100);
    delayMs = constrain(delayMs, 1, 200);

    // Strobe attack LED during blast
    digitalWrite(LED_ALARM_PIN, HIGH);
    for (int i = 0; i < count; i++) {
      udp.beginPacket(targetIP, targetPort);
      // Generate 48 random noise bytes from TRNG
      for (int b = 0; b < 48; b++) {
        udp.write((uint8_t)(esp_random() & 0xFF));
      }
      udp.endPacket();
      packetsInjected++;
      delay(delayMs);
    }
    digitalWrite(LED_ALARM_PIN, LOW);

    Serial.println("{\"status\":\"OK\",\"jammed_packets\":" + String(count) + ",\"target_port\":" + String(targetPort) + "}");
  }
  else if (cmd.startsWith("SET_TARGET ")) {
    // "SET_TARGET <ip> [port]"
    int space1 = cmd.indexOf(' ');
    int space2 = cmd.indexOf(' ', space1 + 1);
    String ipStr = "";
    if (space2 > 0) {
      ipStr = cmd.substring(space1 + 1, space2);
      targetPort = cmd.substring(space2 + 1).toInt();
    } else {
      ipStr = cmd.substring(space1 + 1);
    }
    targetIP.fromString(ipStr);
    Serial.println("{\"status\":\"OK\",\"target_ip\":\"" + targetIP.toString() + "\",\"target_port\":" + String(targetPort) + "}");
  }
  else if (cmd.startsWith("SNIFF ")) {
    // "SNIFF 1" or "SNIFF 0"
    String arg = cmd.substring(6);
    arg.trim();
    if (arg == "1" || arg == "true" || arg == "on") {
      snifferActive = true;
      esp_wifi_set_promiscuous(true);
      esp_wifi_set_promiscuous_rx_cb(&wifiPromiscuousCallback);
      Serial.println("{\"status\":\"OK\",\"sniffer\":\"ACTIVE\"}");
    } else {
      snifferActive = false;
      esp_wifi_set_promiscuous(false);
      Serial.println("{\"status\":\"OK\",\"sniffer\":\"DISABLED\"}");
    }
  }
  else if (cmd == "STATUS") {
    Serial.println("{\"status\":\"ONLINE\",\"role\":\"ATTACKER\",\"firmware\":\"" FIRMWARE_VERSION "\",\"ip\":\"" + WiFi.localIP().toString() + "\",\"target_ip\":\"" + targetIP.toString() + "\",\"target_port\":" + String(targetPort) + ",\"packets_injected\":" + String(packetsInjected) + ",\"trng_bytes\":" + String(trngBytesGenerated) + ",\"alarm\":" + String(attackLedActive ? "true" : "false") + "}");
  }
  else {
    Serial.println("{\"status\":\"ERR\",\"msg\":\"Unknown attacker command\"}");
  }
}
