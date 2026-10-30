# 🌐 Shnik — Quantum-Secured Social Messaging Platform
### Connected with QuSec (Real-World Quantum Cyber-Threat Detection Framework)

[![QuSec Version](https://img.shields.io/badge/QuSec-v0.2.3-00e5ff?style=flat-square)](https://pypi.org/project/qusec/)
[![Website](https://img.shields.io/badge/Live_App-shnik--lake.vercel.app-00e676?style=flat-square)](https://shnik-lake.vercel.app)
[![Protocol](https://img.shields.io/badge/Security-Teleportation_%2B_SARG04-ff0055?style=flat-square)](#-quantum-security-architecture)
[![Hardware](https://img.shields.io/badge/Hardware-Optical_Fibre_%2B_ESP32-ffab00?style=flat-square)](#-hardware-setup--deployment-modes)

---

## 📖 Introduction

**Shnik** ([shnik-lake.vercel.app](https://shnik-lake.vercel.app)) is a next-generation social messaging application integrated with the **QuSec Quantum Cyber-Threat Detection Framework**.

Unlike traditional web messaging apps that rely exclusively on vulnerable public-key math (RSA / ECC), Shnik bridges your browser frontend with a **physical, endpoint-to-endpoint quantum communications transport** running in your local terminal. Messages transmitted through Shnik can be teleported as quantum states across genuine glass optical fiber cables with real-time detection of eavesdropping, dark-fiber disconnects, and channel tampering.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 BROWSER CLIENT (SHNIK)                                 │
│                           https://shnik-lake.vercel.app                                │
│                                                                                        │
│   [ Live Hardware Badges ]     [ Live QBER / Key Pool ]     [ Quantum Pipeline Bar ]   │
│   ● Optical Fibre: Online      Available: 4,820 bits        Encode ➔ Entangle ➔        │
│   ● ESP32 Hardware: Active     QBER: 0.00% (Trusted)        Teleport ➔ Correct         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Local Web Bridge (WebSocket & REST)
                                            │ ws://127.0.0.1:8765/ws  |  http://127.0.0.1:8765
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 LOCAL QUSEC NODE                                       │
│                              Terminal Runtime Engine                                   │
│                                                                                        │
│   • SARG04 Decoy State Engine               • Bell-State Teleportation Core            │
│   • Wegman-Carter Polynomial MAC            • Continuous Key Pool (OTP)                │
│   • Background Carrier Watchdog             • Hoeffding Finite-Size Statistical Bound  │
└───────────────────────┬────────────────────────────────────────┬───────────────────────┘
                        │ USB Serial (115200)                    │ Physical Ethernet
                        ▼                                        ▼
             ┌─────────────────────┐                  ┌─────────────────────┐
             │   ESP32 CONTROLLER  │                  │  OPTICAL CONVERTER  │
             │  • Hardware TRNG    │                  │  • Glass Fibre TX/RX│
             │  • Classical Sync   │                  │  • Qubit State Link │
             │  • Threat LED Alarm │                  │  • Port 9876 UDP    │
             └─────────────────────┘                  └─────────────────────┘
```

---

## ✨ Features of Shnik

### 1. Real-Time Hardware Connectivity Badges
Shnik provides live hardware status directly in the top navigation bar:
- **Optical Fibre Carrier Indicator**:
  - `● GREEN (Active)`: Real physical wired Ethernet/Optical media converter link carrier is detected and photons cross the fiber.
  - `✖ RED (Disconnected)`: Physical optical cable is unplugged, dark, or disconnected.
- **ESP32 Hardware Bridge**:
  - `● GREEN (Connected)`: Physical ESP32 microcontroller detected on USB Serial, providing hardware entropy (`esp_random()`) and classical channel relay.
  - `▲ YELLOW (Simulation)`: Running in high-fidelity software emulation.
- **Entropy Source Badge**: Shows whether random bits originate from hardware quantum avalanche noise or cryptographic CSPRNG.

### 2. Live Quantum Telemetry & Channel Physics
Shnik continuously monitors and visualizes the underlying quantum channel:
- **Quantum Key Pool Gauge**: Displays remaining bits in the secret key pool, consumption rate, and auto-replenishment threshold.
- **QBER (Quantum Bit Error Rate)**: Real-time bit error percentage across test and decoy qubits ($Q \le 6\%$ threshold).
- **Entanglement Fidelity ($F$)**: Measures Bell state preservation ($F \ge 0.98$ in honest channels).
- **CHSH Bell Inequality Parameter ($S$)**: Verifies quantum non-locality ($S \approx 2.82 > 2.0$ proves genuine quantum entanglement).

### 3. Interactive Quantum Pipeline Visualizer
Every message triggers a dynamic pipeline visualization in Shnik:
$$\text{Encode} \longrightarrow \text{Entangle} \longrightarrow \text{Test} \longrightarrow \text{Teleport} \longrightarrow \text{Correct}$$
1. **Encode**: Converts message text into quantum qubit states.
2. **Entangle**: Generates shared EPR Bell pairs $|\Psi^-\rangle_{23}$.
3. **Test**: Injects SARG04 decoy states ($\mu$, $\nu$, vacuum) for eavesdropping detection.
4. **Teleport**: Executes Bell State Measurement (BSM) and transmits quantum states across the optical fiber transceivers (port 9876).
5. **Correct**: Transmits 2-bit classical corrections ($c_0, c_1$) over the ESP32 wireless link and applies Pauli $X$ and $Z$ corrections at the receiver.

### 4. Quantum Public & Private Key Asymmetric Security + QDS
QuSec pairs quantum state teleportation with an asymmetric quantum key architecture and Quantum Digital Signatures (QDS):
- **Quantum Keypair Generation**: Each node (Sender and Receiver) automatically generates an asymmetric `QuantumKeyPair` on initialization:
  - **Quantum Public Key (`Q-PK-...`)**: Exchanged during the initial quantum handshake over the classical ESP32 link. Exposed to the peer and displayed on the Shnik website.
  - **Quantum Private Key (`Q-SK-...`)**: Kept strictly confidential in endpoint memory; never transmitted over the network or exposed in plaintext.
- **Receiver Public Key Encryption**: The sender encrypts the message payload using the **Receiver's Quantum Public Key** (RSA-OAEP 2048 + AES-256-GCM hybrid encapsulation). Only the receiver possessing the corresponding **Quantum Private Key** can decrypt it.
- **Sender Private Key Digital Signature (QDS)**: The sender signs and encrypts a Quantum Digital Signature using its own **Quantum Private Key** (RSA-PSS SHA-256 combined with a 16-bit decoy QDS pattern). This guarantees mathematical non-repudiation and sender authenticity.
- **Dual Physical Transport**:
  - **Optical Fibre Channel (Port 9876 UDP)**: Transmits flying qubits, Bell-state measurement states, and SARG04 decoy states ($\mu, \nu, \text{vac}$) across genuine glass fiber.
  - **ESP32 Classical Channel (Port 9877 UDP / USB Serial)**: Transmits classical Pauli correction coordinates ($c_0, c_1$), encrypted payload, QDS signature, and Wegman-Carter polynomial MAC. Controls the hardware Threat Alarm LED (GPIO 4).

### 5. Genuine Physical Threat Detection & Visual Alarms
- **Optical Cable Unplug Alert**: If the physical optical fiber cable is disconnected during transmission, zero photons arrive. Shnik instantly marks the message as `REJECTED (OPTICAL FIBRE DISCONNECTED)`, blocks message plaintext from displaying, and triggers the hardware threat alarm LED on the ESP32.
- **Channel Tampering / Intercept-Resend Alert**: If an attacker intercepts the optical fiber, statistical error calculation exceeds the Hoeffding bound ($Q > Q_{th}$), generating an alert banner on Shnik.
- **Forgery / Impersonation Alert**: Corrupted classical coordinates or forged MAC tags are blocked before Pauli correction.

---

## 🔗 How to Connect Shnik to Your Terminal

Because **Shnik** is deployed on secure HTTPS ([https://shnik-lake.vercel.app](https://shnik-lake.vercel.app)) and connects to your local machine (`http://127.0.0.1:8765`), web browsers enforce a security policy known as **Private Network Access / Mixed Content**.

Follow these 3 simple steps to link Shnik with your terminal:

### Step 1: Start the QuSec Bridge in Your Terminal

> **Note:** You do **not** type messages into the terminal!  
> The terminal acts as a **Live Transmission Monitor** that displays real-time quantum telemetry, qubit counts, public/private key fingerprints, and threat verification reports. Messages are sent directly from the **[Shnik Website](https://shnik-lake.vercel.app)** or via CLI commands like `qusec send`.

Open your terminal and run:

```bash
# Real hardware mode (Optical Media Converters + ESP32):
qusec bridge --role sender --peer-host 192.168.2.2

# Single-machine simulation mode:
qusec bridge --role sender --sim
```

*(On the receiver laptop or second terminal, run `qusec bridge --role receiver --peer-host 192.168.2.1` or `qusec bridge --role receiver --sim --port 8766`).*

You will see the live QuSec Transmission Monitor banner:
```text
╔══════════════════════════════════════════════════════════════════════════════╗
║    QuSec Quantum Transport & Shnik Web Bridge · [SENDER]                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
 • Hardware Classical Link (ESP32): ONLINE (ESP32 Hardware Connected)
 • Hardware Quantum Link (Optical): ONLINE (Glass Fibre Connected)
 • Node Role:                      Sender (Peer: Receiver)
 • Quantum Public Key:             Q-PK-SENDER-A41B-97E2-6C81-5401
 • Quantum Private Key:            Q-SK-SENDER-A41B-97E2-6C81-5401 [Secured in Memory]
 • Peer Quantum Public Key:        Q-PK-RECV-7E43-1289-54AA-19BF
 • Platform Gateway Server:        http://0.0.0.0:8765
 • Connected Web Application:      https://shnik-lake.vercel.app
 • Active Key Pool:                4,820 bits
╠══════════════════════════════════════════════════════════════════════════════╣
 Mode: Live Transmission Monitor. Transmissions from website or library
 commands stream here automatically. User does not type in terminal.
 Press Ctrl+C to stop.
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

### Step 2: Configure Browser Permission (One-Time Setup)

By default, Google Chrome, Brave, and Microsoft Edge block public HTTPS pages from calling local `http://127.0.0.1`. You must allow local connections for `shnik-lake.vercel.app`:

1. Open **[https://shnik-lake.vercel.app](https://shnik-lake.vercel.app)** in your browser.
2. Click the **View site information / Padlock / Tune** icon on the far left of the browser URL bar:
   ```text
   ┌──────────────────────────────────────────────────────────┐
   │ 🔒 [tune icon] https://shnik-lake.vercel.app             │
   └──────────────────────────────────────────────────────────┘
   ```
3. Click **Site settings**.
4. Scroll down to find **Insecure content** (or **Private network access**).
5. Change the dropdown setting from **Block (default)** to **Allow**.
6. Close the settings tab and click **Reload / Refresh** on Shnik.

---

### Step 3: Transmit Messages & View Live Terminal Stream

After reloading:
- The top-right status badge in Shnik will illuminate **GREEN**:
  ```text
  ● QuSec Node Online | Quantum Fibre: Connected | ESP32: Active
  ```
- Send any message from the **Shnik Website** ([shnik-lake.vercel.app](https://shnik-lake.vercel.app)).
- The sender terminal instantly renders the **Outgoing Quantum Transmission** report:
  ```text
  ══ 🚀 QUSEC OUTGOING QUANTUM TRANSMISSION ══
  ┌──────────────────────────────┬───────────────────────────────────────────────┐
  │ Parameter                    │ Value / Measurement                           │
  ├──────────────────────────────┼───────────────────────────────────────────────┤
  │ Session ID                   │ a91f                                          │
  │ Transmission Direction       │ Sender ➔ Receiver                             │
  │ Plaintext Message            │ "Hello from Shnik!"                           │
  │ Receiver Quantum Public Key  │ Q-PK-RECV-7E43-1289-54AA-19BF (Encrypted)     │
  │ Sender Quantum Private Key   │ Q-SK-SENDER-A41B-97E2-6C81-5401 (QDS Signed)  │
  │ Optical Channel (Fibre)      │ 248 Qubits Dispatched (Port 9876)             │
  │ ESP32 Classical Channel      │ Pauli bits X=120, Z=128 & MAC (Port 9877)     │
  │ Channel Status               │ Active (Photons Crossing Glass Fibre)         │
  └──────────────────────────────┴───────────────────────────────────────────────┘
  ```
- The receiver terminal instantly decrypts the message with its **Quantum Private Key**, verifies the **Sender Quantum Public Key**, and renders the **Quantum Security Report**:
  ```text
  ══ QUSEC QUANTUM SECURITY REPORT ══
  ┌──────────────────────────────┬───────────────────────────────────────────────┐
  │ Parameter                    │ Value / Measurement                           │
  ├──────────────────────────────┼───────────────────────────────────────────────┤
  │ Session ID                   │ a91f                                          │
  │ Receiver Quantum Private Key │ Q-SK-RECV-7E43-1289-54AA-19BF (Decrypted)     │
  │ Sender Quantum Public Key    │ Q-PK-SENDER-A41B-97E2-6C81-5401 (Verified)    │
  │ Quantum Digital Signature    │ VERIFIED (Cryptographic Non-Repudiation)      │
  │ Decrypted Message Plaintext  │ "Hello from Shnik!"                           │
  │ Calculated QBER              │ 0.00% (Threshold: 6.00%)                      │
  │ Hardware Threat Alarm        │ CLEAR (ESP32 Second LED OFF)                  │
  └──────────────────────────────┴───────────────────────────────────────────────┘
  ```

> **💡 Zero-Configuration Alternative (Built-in Local Web Chat):**  
> If you prefer not to change browser permissions, open the locally hosted web chat served directly by your QuSec node:  
> **`http://127.0.0.1:8765/`** or **`http://localhost:8765/chat`**  
> *(Has 100% identical visuals with zero mixed-content restrictions).*

---

## 💻 Complete QuSec CLI Command Reference

Below is the complete reference for all available `qusec` commands in your terminal:

### 1. `qusec doctor` (Diagnostics & Hardware Self-Test)
Runs a diagnostic verification of all quantum libraries, physical USB serial ports, Ethernet network adapters, and optical carrier signals.

```bash
# Basic hardware and software check:
qusec doctor

# Hardware check with active optical fiber probe to peer laptop:
qusec doctor --peer-host 192.168.2.2
```

**Output Breakdown:**
- **Software Dependencies**: Verifies Python $\ge 3.9$, Qiskit, Qiskit Aer, PySerial, WebSockets.
- **ESP32 Detection**: Lists USB-UART bridge chips (CP2102, CH340, FTDI) and verifies hardware TRNG.
- **Optical NIC Detection**: Filters out Wi-Fi/Bluetooth and tests physical 802.3 wired Ethernet media converter NICs.
- **End-to-End Carrier Probe**: Pings peer across optical subnet (`192.168.2.x`) to verify light transmission through glass fiber.

---

### 2. `qusec chat` (Continuous Two-Way Quantum Chat)
Starts a full-duplex interactive quantum chat console in the terminal. Automatically starts the Shnik web bridge gateway on port 8765.

```bash
# Hardware mode on Sender Laptop:
qusec chat --role sender --peer-host 192.168.2.2

# Hardware mode on Receiver Laptop:
qusec chat --role receiver --peer-host 192.168.2.1

# Software simulation mode (Single laptop test):
qusec chat --role sender --sim
qusec chat --role receiver --sim
```

**Interactive In-Chat Commands:**
- `/status` — View current session ID, key pool bits, QBER, and fidelity.
- `/rekey` — Manually trigger an entanglement distribution round to replenish key material.
- `/attack tampering` — Simulate optical channel disturbance to test threat detection.
- `/attack forgery` — Simulate MAC tag corruption to test authentication rejection.
- `/attack none` — Restore channel to honest mode.
- `/quit` or `/exit` — Shutdown the quantum transport gracefully.

---

### 3. `qusec node` (Live Terminal Dashboard)
Launches the full rich terminal UI dashboard featuring real-time pipeline progress bars, channel security meters, and message log tables.

```bash
qusec node --role sender --peer-host 192.168.2.2
qusec node --role receiver --peer-host 192.168.2.1

# Run in simulation mode for 60 seconds then stop:
qusec node --role sender --sim --duration 60
```

---

### 4. `qusec gateway` (Headless Platform Bridge API)
Runs the HTTP REST, SSE, and WebSocket gateway server in the background for social media platforms and web apps like Shnik, without prompting for terminal input.

```bash
# Start gateway on default port 8765:
qusec gateway --role sender --peer-host 192.168.2.2

# Start gateway on custom port with specific ESP32 serial port:
qusec gateway --role sender --port 8765 --esp32-port /dev/cu.usbserial-0001
```

**Gateway Endpoints Exposed:**
- `GET  /api/status` or `/status` — Node health, key pool size, optical link state.
- `GET  /api/messages` or `/messages` — List of recent quantum decrypted messages.
- `GET  /api/events` or `/events` — Real-time Server-Sent Events (SSE) stream.
- `GET  /ws` or `/` — RFC 6455 bidirectional WebSocket connection.
- `POST /api/send` or `/send` — Transmit message (`{"text": "...", "mode": "teleportation"}`).
- `POST /api/session/init` or `/init` — Trigger new quantum handshake.
- `POST /api/rekey` or `/rekey` — Request key replenishment round.

---

### 5. `qusec keys` (Key Pool Inspection)
Inspects the cryptographic health, entropy lifecycle, and available secret bits of the running node.

```bash
qusec keys

# Inspect key pool on custom gateway port:
qusec keys --gateway-url http://127.0.0.1:8765/api/status
```

---

### 6. `qusec send` (One-Shot CLI Message Transmission)
Transmits a single message directly from command line arguments via teleportation or OTP.

```bash
# Send via Quantum Teleportation:
qusec send "Top Secret Quantum Payload" --to receiver --mode teleportation

# Send via Information-Theoretic One-Time Pad:
qusec send "Cryptographic OTP Payload" --to receiver --mode otp
```

---

### 7. `qusec run` (Circuit Simulation & Attack Verification)
Runs the legacy interactive circuit simulation benchmark, providing step-by-step mathematical output of the quantum states.

```bash
# Run simulator with 2,000 shots:
qusec run --shots 2000 --threshold 0.05

# Run under simulated intercept-resend attack:
qusec run --attack intercept_resend

# Output machine-readable JSON for automated benchmarking:
qusec run --json
```

---

### 8. `qusec version`
Prints the installed QuSec framework version:

```bash
qusec version
# Output: QuSec v0.2.3
```

---

## 🛠️ Complete CLI Options Matrix

| Flag | Applicable Commands | Default | Description |
|:-----|:--------------------|:--------|:------------|
| `--role` | `chat`, `node`, `gateway` | `sender` | Node role: `sender` (Alice) or `receiver` (Bob) |
| `--peer-host` | `doctor`, `chat`, `node`, `gateway` | `127.0.0.1` | IP address of peer laptop across the optical transceiver link |
| `--optical-port` | `chat`, `node` | `9876` | UDP port for optical quantum burst frames |
| `--classical-port` | `chat`, `node` | `9877` | UDP port for classical synchronization frames |
| `--gateway-port` | `chat`, `node`, `gateway` | `8765` | HTTP and WebSocket port for Shnik web bridge |
| `--esp32-port` | `chat`, `node`, `gateway` | Auto-detect | Specific serial port for ESP32 (e.g., `/dev/cu.usbserial-110` or `COM3`) |
| `--sim` | `chat`, `node`, `gateway` | `False` | Force software simulation mode without physical hardware |
| `--hardware` | `node` | `False` | Prefer physical hardware over simulation |
| `--duration` | `node` | `None` | Automatically exit after $N$ seconds |
| `--mode` | `send` | `teleportation` | Encryption/Transport mode: `teleportation` or `otp` |
| `--shots` | `run` | `1000` | Number of measurement shots for state evaluation |
| `--threshold` | `run` | `0.06` | Maximum acceptable QBER before flagging an alarm |

---

## 🔌 Hardware Setup & Deployment Modes

### Scenario 1: Dual Laptop Real Hardware Setup (Back-to-Back Optical Link)

This is the physical demonstration setup using two laptops connected by fiber transceivers:

```text
Laptop A (Sender)                                              Laptop B (Receiver)
IP: 192.168.2.1                                                IP: 192.168.2.2
┌─────────────────────────┐                                    ┌─────────────────────────┐
│ • Terminal:             │                                    │ • Terminal:             │
│   qusec chat            │                                    │   qusec chat            │
│   --role sender         │                                    │   --role receiver       │
│   --peer-host           │                                    │   --peer-host           │
│   192.168.2.2           │                                    │   192.168.2.1           │
│                         │                                    │                         │
│ • Browser:              │                                    │ • Browser:              │
│   shnik-lake.vercel.app │                                    │   shnik-lake.vercel.app │
└────────────┬────────────┘                                    └────────────┬────────────┘
             │ Ethernet                                                     │ Ethernet
┌────────────▼────────────┐                                    ┌────────────▼────────────┐
│ Optical Media Converter │══════ Yellow Optical Fibre Cable ══│ Optical Media Converter │
│ IP: 192.168.2.1         │           (Single Mode)            │ IP: 192.168.2.2         │
└─────────────────────────┘                                    └─────────────────────────┘
```

#### Step-by-Step Hardware Configuration:
1. **Configure Laptop A Ethernet IP**:
   - Subnet Mask: `255.255.255.0`
   - IPv4 Address: `192.168.2.1`
2. **Configure Laptop B Ethernet IP**:
   - Subnet Mask: `255.255.255.0`
   - IPv4 Address: `192.168.2.2`
3. **Connect Optical Transceivers**:
   - Plug Ethernet cable from Laptop A to Transceiver A.
   - Plug Ethernet cable from Laptop B to Transceiver B.
   - Connect the optical fiber cable between Transceiver A (TX) and Transceiver B (RX).
4. **Plug in ESP32 Microcontrollers**:
   - Connect ESP32 A to Laptop A via USB.
   - Connect ESP32 B to Laptop B via USB.
5. **Verify with Doctor**:
   - On Laptop A: `qusec doctor --peer-host 192.168.2.2`
   - On Laptop B: `qusec doctor --peer-host 192.168.2.1`
   - Confirm: `● Active (Optical Carrier Verified across Glass Fibre)`.
6. **Start Chat & Open Shnik**:
   - Laptop A: `qusec chat --role sender --peer-host 192.168.2.2`
   - Laptop B: `qusec chat --role receiver --peer-host 192.168.2.1`
   - Open **[shnik-lake.vercel.app](https://shnik-lake.vercel.app)** on both laptops.

---

### Scenario 2: Single Laptop Simulation Setup

Test the entire stack on a single machine without any cables or microcontrollers:

1. **Terminal 1 (Sender):**
   ```bash
   qusec chat --role sender --sim
   ```
2. **Terminal 2 (Receiver):**
   ```bash
   qusec chat --role receiver --sim
   ```
3. **Open Browser:**
   - Go to [shnik-lake.vercel.app](https://shnik-lake.vercel.app) (Sender on port 8765)
   - Or open `http://127.0.0.1:8766/` for Receiver (port 8766)
4. Send messages back and forth and watch the live quantum pipeline!

---

## 🔬 JavaScript Web Bridge SDK (`qusec-web-bridge.js`)

If you want to integrate the QuSec quantum transport into any custom frontend or dashboard, use the built-in JavaScript SDK:

```javascript
// Initialize connection to local QuSec node
const qusec = new QuSecBridge("http://127.0.0.1:8765");

// 1. Listen for real-time status updates (Hardware, Key Pool, QBER)
qusec.onStatus((status) => {
  console.log("Session ID:", status.session_id);
  console.log("Fibre Status:", status.channel.fibre_ok ? "Online" : "Dark/Unplugged");
  console.log("Available Keys:", status.key_pool.available_bits);
  console.log("QBER:", (status.channel.qber * 100).toFixed(2) + "%");
});

// 2. Listen for incoming decrypted messages
qusec.onMessage((msg) => {
  console.log(`Received from ${msg.from}: "${msg.text}" via ${msg.mode}`);
  if (msg.threat) {
    alert(`SECURITY THREAT: Message blocked! ${msg.decision}`);
  }
});

// 3. Connect WebSocket and start live polling
qusec.start();

// 4. Send a message via Quantum Teleportation
async function handleSend() {
  const result = await qusec.sendMessage("Hello via Quantum Teleportation!", "teleportation");
  console.log("Teleportation result:", result);
}
```

---

## ❓ Troubleshooting & FAQs

### Q1: Shnik shows "OFFLINE" or a RED status badge.
- **Cause**: The local QuSec node is not running, or your browser is blocking local HTTP calls.
- **Fix**:
  1. Verify the terminal is running `qusec chat` or `qusec gateway`.
  2. Check `http://127.0.0.1:8765/status` in a new browser tab.
  3. Ensure you allowed **Insecure content** in Chrome/Brave/Edge site settings for `shnik-lake.vercel.app`.

### Q2: Optical Fibre shows "Disconnected" even when plugged in.
- **Cause**: The Ethernet interface is not assigned to the `192.168.2.x` subnet, or the optical fiber cable is plugged backwards (TX must connect to RX).
- **Fix**:
  1. Swap the two fiber LC/SC connectors on one transceiver (TX ➔ RX).
  2. Ensure Laptop A is `192.168.2.1` and Laptop B is `192.168.2.2`.
  3. Run `qusec doctor --peer-host 192.168.2.2` to test light reachability.

### Q3: How do I test the physical disconnect alarm?
- **Test**:
  1. Start chat on both laptops with fiber connected.
  2. Unplug the yellow optical fiber cable.
  3. Send a message from Shnik.
  4. Notice:
     - Message is blocked with `REJECTED (OPTICAL FIBRE DISCONNECTED)`.
     - ESP32 Second LED starts blinking rapidly (Threat Alarm).
     - Status badge turns RED on Shnik.
  5. Plug the cable back in — the carrier watchdog restores the link to GREEN within 1.2 seconds!

---

## 📄 License
This project is licensed under the **MIT License**.
