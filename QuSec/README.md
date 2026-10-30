<h1 align="center">QuSec - Quantum Security Framework</h1>

<p align="center">
  <img src="QuSec GitHub README banner.png" alt="QuSec Banner">
</p>
## Description
QuSec is a comprehensive Quantum Security Framework designed for Quantum Digital Signature (QDS) threat detection.

## Introduction
It leverages Qiskit to simulate a quantum-safe teleportation-based QDS protocol layered with the SARG04 decoy-state method to detect active tampering, forgery, and interception attacks.

## PyPI Link
[QuSec on PyPI](https://pypi.org/project/qusec/)

## 🚀 Features

- **Quantum Asymmetric Cryptosystem**: Generates `QuantumPublicKey` (`Q-PK-...`) and `QuantumPrivateKey` (`Q-SK-...`) pairs for Sender and Receiver. Encrypts plaintext payloads using the receiver's Quantum Public Key and signs/encrypts Quantum Digital Signatures (QDS) using the sender's Quantum Private Key.
- **Dual Physical Channel Architecture**:
  - **Optical Link (UDP 9876 / Glass Fiber)**: Carries flying qubits, Bell-state teleportation frames, and SARG04 decoy states.
  - **ESP32 Classical Channel (UDP 9877 / USB Serial)**: Exchanges classical Pauli corrections ($c_0, c_1$), ciphertext payloads, QDS signatures, Wegman-Carter MACs, and drives the hardware threat alarm LED (GPIO 4).
- **Web App Bridge Integration**: Seamless integration with the [Shnik Platform](https://shnik-lake.vercel.app) where the terminal streams live transmissions without requiring user terminal input.
- **Teleportation-Based QDS**: Transmits signature payload using a 3-qubit Bell-state entanglement and Pauli corrections.
- **SARG04 Protocol Integration**: Employs mathematical decoy states ($\mu$, $\nu$, vacuum) for sifting and quantum channel security.
- **Attack Simulations**: Test real-time quantum threat vectors including Forgery, Impersonation, Intercept-Resend, Replay, and Channel Tampering.
- **Multi-Backend Execution**:
  - `Simulator`: Ideal local execution via Qiskit Aer.
  - `Noisy`: Local simulation mapped with a configurable depolarizing noise model.
  - `Hardware`: Secure execution loop ready for real IBM Quantum API connections.
- **Dynamic Threat Analysis**: Dynamically calculates Quantum Bit Error Rate (QBER) and statistically evaluates it against security thresholds.

---

## 📦 Installation Guide

To install QuSec, ensure you have Python 3.9+ installed.

### 1. Set up a virtual environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

### 2. Install QuSec
Install QuSec directly in editable mode for local development:
```bash
pip install -e .
```

*(Optional)* If you plan on running your circuits on real IBM Quantum Hardware, install the hardware add-on:
```bash
pip install -e ".[hardware]"
```

---

## 💻 Quickstart

QuSec comes with a beautiful, fully-interactive Terminal User Interface (TUI). 

To launch the framework and start a secure message transfer, simply run:
```bash
qusec run
```

### Advanced Usage Flags
You can skip the interactive menus by passing parameters directly to the CLI:

- **View detailed transmission steps (Bit-by-Bit):**
  ```bash
  qusec run --verbose
  ```
- **Select a specific execution backend:**
  ```bash
  qusec run --backend noisy
  ```
- **Machine-readable JSON output (Great for CI/CD or logging):**
  ```bash
  qusec run --json
  ```
- **Tweak the mathematical constraints:**
  ```bash
  qusec run --shots 2000 --threshold 0.04
  ```

Run `qusec run --help` to see all available configuration options!

---

## 🛡️ Simulating Attacks

When using the interactive simulator (`qusec run`), you will be prompted to simulate a cyberattack vector.

1. **No Attack**: The message transfers securely. QBER remains $0.0$, and the signature is `VERIFIED`.
2. **Forgery / Impersonation**: Attempting to supply fake signature data. The verification layer catches the mathematical anomaly and blocks the transmission: `REJECTED`.
3. **Quantum Channel Tampering**: Induces simulated `X` and `Z` errors in the teleportation channel. You will see the QBER instantly spike above the defined threshold (default `0.06`), triggering a `THREAT DETECTED` system halt.

---

## 🌐 Real-World Hardware & Transport Architecture

QuSec has been upgraded into a functional, real-world secure transport framework:

```text
Sender Laptop                                       Receiver Laptop
┌───────────────────────┐                           ┌───────────────────────┐
│ QuSec Node (Sender)   │                           │ QuSec Node (Receiver) │
│  ├── Gateway API      │                           │  ├── Gateway API      │
│  ├── Key Pool         │                           │  ├── Key Pool         │
│  └── Teleport Engine  │                           │  └── Teleport Engine  │
└──────────┬────────────┘                           └───────────┬───────────┘
           │ USB Serial                                         │ USB Serial
┌──────────▼────────────┐                           ┌───────────▼───────────┐
│ ESP32 Sender          │◄─── Classical Wireless ──►│ ESP32 Receiver        │
│ (TRNG + Wi-Fi Relay)  │     (Wi-Fi / ESP-NOW)     │ (TRNG + Wi-Fi Relay)  │
└───────────────────────┘                           └───────────────────────┘
           │ Ethernet                                           │ Ethernet
┌──────────▼────────────┐                           ┌───────────▼───────────┐
│ Optical Transceiver   │◄════ Optical Fibre Cable ═►│ Optical Transceiver   │
│ Media Converter       │     (Quantum Channel)     │ Media Converter       │
└───────────────────────┘                           └───────────────────────┘
```

### Components
1. **4 ESP32 Microcontrollers**: Sender, Receiver, Attacker (Eve), and Auditor (QAuditor).
2. **Optical Transceivers & Fibre Cable**: Full-duplex optical transceiver pair carrying quantum distribution and teleportation frames over Ethernet.
3. **2 Ethernet Cables**: Connecting Sender and Receiver laptops to their respective optical media converters.
4. **Auto-Detection**: QuSec automatically probes USB serial ports (`/dev/cu.usbserial*`, `/dev/ttyUSB*`) to detect ESP32 hardware and network interfaces to detect Ethernet converters.

> **Honest Note on Security Model**: Key creation, reconciliation, and OTP encryption execute on the laptop endpoints. The browser-to-gateway hop is local plaintext. The system provides **laptop-to-laptop quantum-secure** transport.

---

## 🛠️ CLI Commands

### 1. Link Diagnostics (`qusec doctor`)
Self-test verifying Python environment, ESP32 USB detection, hardware TRNG entropy, Ethernet media converter link, and socket bindings:
```bash
qusec doctor
```

### 2. Website & Platform Bridge Monitor (`qusec bridge`)
Connects the terminal directly to the [Shnik Web App](https://shnik-lake.vercel.app), ESP32 classical channel, and optical quantum channel in **Live Transmission Monitor** mode:
```bash
# On Sender Laptop (Connected to ESP32 and Optical Transceiver):
qusec bridge --role sender --peer-host <RECEIVER_OPTICAL_IP>

# On Receiver Laptop:
qusec bridge --role receiver --peer-host <SENDER_OPTICAL_IP>

# Single Laptop Simulation Test:
qusec bridge --role sender --sim
qusec bridge --role receiver --sim --port 8766
```
- **Zero Terminal Message Prompting**: You do not type messages in the terminal. The terminal acts as a dedicated live transmission console.
- **Real-Time Transmission Stream**: Messages triggered from the website or library commands (`qusec send`) instantly render outgoing quantum transmission tables on the sender and incoming security reports on the receiver.
- **Quantum Public & Private Key Fingerprints**: Shows sender private key signing and receiver public key encryption in real time.

### 3. Continuous Interactive Quantum Chat (`qusec chat`)
Runs continuous two-way interactive quantum chat directly in your terminal:
```bash
# On Sender Laptop:
qusec chat --role sender

# On Receiver Laptop:
qusec chat --role receiver --peer-host <SENDER_IP>
```
- Real-time two-way messaging with quantum state teleportation.
- Auto-initializes entanglement and key pool as soon as the first message is sent.
- Concurrently runs the background Web Platform Gateway (`http://127.0.0.1:8765`) for social media website integration.
- Loops continuously until you turn it off (`/quit` or `Ctrl+C`).
- To run without typing prompt (monitor mode): `qusec chat --role sender --monitor`

### 4. Interactive Node & Live UI Dashboard (`qusec node`)
Launches the live operational terminal dashboard:
```bash
# On Sender Laptop:
qusec node --role sender

# On Receiver Laptop:
qusec node --role receiver --peer-host <SENDER_IP>
```

#### Terminal UI Display:
```
┌ QuSec · Sender ────────────── ● Fibre OK  ● ESP32 OK ┐
│ Session a91f · Key pool 4,820 bits · QBER 2.1%       │
├ Pipeline ────────────────────────────────────────────┤
│ Encode ✓  Entangle ✓  Test ✓  Teleport ▶  Correct ·  │
├ Log ─────────────────────────────────────────────────┤
│ 14:02:11 Bell pairs sent: 512 (64 test pairs)        │
│ 14:02:12 Fidelity 0.97, CHSH 2.71 → channel trusted  │
└──────────────────────────────────────────────────────┘
```

### 5. Social Media Platform Bridge Gateway (`qusec gateway`)
Starts the local REST + SSE platform bridge for web applications:
```bash
qusec gateway --role sender --port 8765
```
- `GET  /api/status` : Node status, active session, key pool, and quantum channel metrics.
- `POST /api/send`   : Send message (`{"to": "receiver", "message": "...", "mode": "teleportation"|"otp"}`).
- `GET  /api/events` : Real-time Server-Sent Events (SSE) stream.
- `POST /api/rekey`  : Trigger key pool replenishment round.

### 6. Key Pool Inspector (`qusec keys`)
Inspects active cryptographic key material, rekey triggers, and burn-on-use stats:
```bash
qusec keys
```

### 7. Quantum-Secure Send (`qusec send`)
Transmits a message over the quantum link via state teleportation or One-Time-Pad:
```bash
qusec send "Hello Quantum Teleportation" --to receiver --mode teleportation
qusec send "Top Secret" --to receiver --mode otp
```

---

## ⚡ ESP32 Firmware

The ready-to-flash Arduino C++ firmware is provided in:
`firmware/esp32_qusec/esp32_qusec.ino`

Flash to each ESP32 board using Arduino IDE or PlatformIO:
- True Hardware RNG via `esp_random()`
- Wi-Fi Access Point / Station Classical Relay (Port `9877`)
- Serial protocol interface at `115200` baud


