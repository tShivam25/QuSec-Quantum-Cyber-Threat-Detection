# Quantum Channel Monitoring System (QCMS)

A real-world quantum-secured communication and channel surveillance system combining **quantum-secure teleportation transport** with **real-time channel threat auditing**.

---

## 🏛️ Repository Architecture

This repository is organized into two primary frameworks:

```text
Quantum-Channel-Monitoring-System/
├── QuSec/                     # Quantum-Secure Transport & Teleportation Framework
│   ├── src/qusec/             # Core Python library (Node runtime, Quantum, Hardware, Crypto)
│   ├── tests/                 # Unit & integration test suites
│   ├── firmware/              # ESP32 C++ firmware for hardware TRNG & classical relay
│   ├── web/                   # Web platform bridge SDK & live browser testbench
│   ├── pyproject.toml         # Standalone pip package configuration
│   └── README.md              # In-depth QuSec documentation & CLI guide
│
├── QAuditor/                  # Quantum Channel Threat Auditing & Monitoring (Upcoming)
│   └── ...                    # Active eavesdropping detection, QBER telemetry & auditor nodes
│
└── README.md                  # System overview & hardware topology
```

---

## 🔬 System & Hardware Architecture

The end-to-end setup implements a physical 4-node quantum communication and auditing topology:

```text
Sender Laptop                                       Receiver Laptop
┌───────────────────────┐                           ┌───────────────────────┐
│ QuSec Node (Sender)   │                           │ QuSec Node (Receiver) │
│  ├── Gateway REST/SSE │                           │  ├── Gateway REST/SSE │
│  ├── Key Pool (OTP)   │                           │  ├── Key Pool (OTP)   │
│  └── Teleport Engine  │                           │  └── Teleport Engine  │
└──────────┬────────────┘                           └───────────┬───────────┘
           │ USB Serial (115200)                                │ USB Serial (115200)
┌──────────▼────────────┐                           ┌───────────▼───────────┐
│ ESP32 Sender          │◄─── Classical Wireless ──►│ ESP32 Receiver        │
│ (TRNG + Wi-Fi Relay)  │     (Wi-Fi / ESP-NOW)     │ (TRNG + Wi-Fi Relay)  │
└───────────────────────┘                           └───────────────────────┘
           │ Ethernet                                           │ Ethernet
┌──────────▼────────────┐                           ┌───────────▼───────────┐
│ Optical Transceiver   │◄════ Optical Fibre Cable ═►│ Optical Transceiver   │
│ Media Converter       │     (Quantum Channel)     │ Media Converter       │
└───────────────────────┘                           └───────────────────────┘
           ▲                                                    ▲
           │                                                    │
     [Attacker / Eve]                                    [Auditor / QAuditor]
     ESP32 + Intercept                                   ESP32 + QBER Probe
```

### Physical Hardware Components
1. **4 ESP32 Microcontrollers**:
   - **Sender ESP32**: Generates quantum randomness via hardware `esp_random()` TRNG and acts as the sender's classical Wi-Fi bridge.
   - **Receiver ESP32**: Coordinates classical reconciliation frames and timing synchronization.
   - **Attacker ESP32 (Eve)**: Intercept-resend and channel disturbance simulator.
   - **Auditor ESP32 (QAuditor)**: Independent channel surveillance and telemetry probe.
2. **Optical Transceiver Pair & Fibre Cable**:
   - Media converters connecting via high-speed optical fibre carrying simulated quantum carrier frames over Ethernet.
3. **2 Ethernet Cables**:
   - Direct physical connection between Sender Laptop and Optical Media Converter, and between Receiver Laptop and Optical Media Converter.
4. **Endpoint Laptops**:
   - Running full-duplex QuSec nodes, local quantum circuit emulation (Qiskit / Aer), and social media web bridge gateways.

---

## ⚡ Quickstart: QuSec Package

`QuSec` is a fully standalone Python package packaged under the `QuSec/` directory.

### Installation

#### Option 1: Install from Local Clone
```bash
git clone https://github.com/tShivam25/Quantum-Channel-Monitoring-System.git
cd Quantum-Channel-Monitoring-System/QuSec
pip install -e .
```

#### Option 2: Direct Global Installation via Pip
```bash
pip install "git+https://github.com/tShivam25/Quantum-Channel-Monitoring-System.git#subdirectory=QuSec"
```

### Diagnostics & Self-Test
Verify all hardware, serial ports, and network channels:
```bash
qusec doctor
```

### Continuous Interactive Quantum Chat
Start continuous two-way quantum chat directly in your terminal (loops continuously until you turn it off):
```bash
# On Sender Laptop:
qusec chat --role sender

# On Receiver Laptop:
qusec chat --role receiver --peer-host <SENDER_IP>
```

### Run Live Visual Dashboard Node
```bash
# On Sender Laptop:
qusec node --role sender

# On Receiver Laptop:
qusec node --role receiver --peer-host <SENDER_IP>
```

### Launch Attacker Console on 3rd Laptop (`qusec attacker`)
Connect the Attacker ESP32 to the 3rd laptop and start the Claude Code styled adversary console:
```bash
# Interactive Claude Code TUI:
qusec attacker --target-host <RECEIVER_IP>

# Automated random in-between chat attacks:
qusec attacker --target-host <RECEIVER_IP> --random
```

For complete technical specifications, mathematical protocols (SARG04 + 3-qubit Bell teleportation), and REST API documentation, see the [QuSec Subdirectory Documentation](QuSec/README.md).


---

## 📄 License
MIT License.
