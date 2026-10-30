<h1 align="center">QuSec - Quantum Security Framework</h1>

<p align="center">
  <img src="QuSec GitHub README banner.png" alt="QuSec Banner">
</p>
## Description
QuSec is a comprehensive Quantum Security Framework designed for Quantum Digital Signature (QDS) threat detection, asymmetric quantum key encapsulation, and full-duplex social messaging transport.

## Introduction
It leverages Qiskit and Qiskit Aer to simulate a quantum-safe teleportation-based QDS protocol layered with the SARG04 decoy-state method, calibrated depolarizing noise models, and real IBM Quantum cloud hardware execution to detect active tampering, forgery, and interception attacks in real time.

## PyPI Link
[QuSec on PyPI](https://pypi.org/project/qusec/)

---

## 🚀 Features

- **Dual-Mode Bidirectional Social Chatting**: Full-duplex two-way transmission across two laptops connected via the [Shnik Platform](https://shnik-lake.vercel.app). Both laptops function concurrently as Sender and Receiver.
- **3 Quantum Execution Backends**:
  1. `AerSimulator`: Ideal local quantum statevector / matrix simulation via Qiskit Aer ($Q_0 = 0.0\%$).
  2. `Noisy AerSimulator`: Calibrated fiber channel depolarizing gate error (0.3% 1-qubit, 0.4% 2-qubit CX) & thermal relaxation ($Q_0 \approx 1.0\%$).
  3. `Quantum Hardware`: Real IBM Quantum superconducting QPUs via `qiskit-ibm-runtime` (e.g., `ibm_kyoto`, `ibm_sherbrooke`).
- **Mathematical Auto-Adjusting QBER Threshold**: Threshold mathematically self-adjusts based on message length $n$, Raman scattering traffic noise $\Phi$, and channel drift $\bar{Q}_{\text{ema}}$ with finite-size Hoeffding concentration bounds at $99.9\%$ confidence.
- **Quantum Asymmetric Cryptosystem**: Generates `QuantumPublicKey` (`Q-PK-...`) and `QuantumPrivateKey` (`Q-SK-...`) pairs for Sender and Receiver. Encrypts plaintext payloads using the receiver's Quantum Public Key and signs/encrypts Quantum Digital Signatures (QDS) using the sender's Quantum Private Key.
- **Dual Physical Channel Architecture**:
  - **Optical Link (UDP 9876 / Glass Fiber)**: Carries flying qubits, Bell-state teleportation frames, and SARG04 decoy states.
  - **ESP32 Classical Channel (UDP 9877 / USB Serial)**: Exchanges classical Pauli corrections ($c_0, c_1$), ciphertext payloads, QDS signatures, Wegman-Carter MACs, and drives the hardware threat alarm LED (GPIO 4).
- **Web App Bridge Integration**: Seamless integration with the [Shnik Platform](https://shnik-lake.vercel.app) where the terminal streams live transmissions without requiring user terminal input.
- **Teleportation-Based QDS**: Transmits signature payload using 3-qubit Bell-state entanglement and conditional Pauli corrections ($Z^{c_0} X^{c_1}$).
- **SARG04 Protocol Integration**: Employs mathematical decoy states ($\mu$, $\nu$, vacuum) for sifting and quantum channel security.
- **Attack Simulations**: Test real-time quantum threat vectors including Forgery, Impersonation, Intercept-Resend, Replay, and Channel Tampering.

---

## 🔄 Dual-Mode Bidirectional Social Chatting (Laptop A ⇄ Laptop B)

QuSec enables full-duplex, two-way chatting across two separate laptops connected via the **Shnik Web App** ([https://shnik-lake.vercel.app](https://shnik-lake.vercel.app)). Both endpoints act as both Sender and Receiver in a symmetric peer-to-peer topology.

```text
Laptop A (Peer A)                                                Laptop B (Peer B)
┌─────────────────────────────────┐                             ┌─────────────────────────────────┐
│ Browser: shnik-lake.vercel.app  │                             │ Browser: shnik-lake.vercel.app  │
│ Types: "hello"                  │                             │ Receives: "hello"               │
│ Receives: "i am fine"           │                             │ Types: "i am fine"              │
└───────────────┬─────────────────┘                             └───────────────┬─────────────────┘
                │ Local REST/SSE (Port 8765)                                    │ Local REST/SSE (Port 8765)
┌───────────────▼─────────────────┐                             ┌───────────────▼─────────────────┐
│ QuSec Terminal Engine (Dual)    │◄════ Optical Fibre (9876) ═►│ QuSec Terminal Engine (Dual)    │
│ Displays Security Report B ➔ A  │◄─── ESP32 Classical (9877) ─►│ Displays Security Report A ➔ B  │
└─────────────────────────────────┘                             └─────────────────────────────────┘
```

### Transmission Flow
1. **Laptop A transmits**: User writes `"hello"` on the Shnik website on Laptop A.
2. **Laptop B receives**: Laptop B displays `"hello"` on the Shnik website, and the Laptop B terminal automatically outputs the live **QuSec Quantum Security Report** (calculating QBER, Hoeffding margin, and verifying QDS signature).
3. **Laptop B replies**: User writes `"i am fine"` on the Shnik website on Laptop B.
4. **Laptop A receives**: Laptop A displays `"i am fine"` on the Shnik website, and the Laptop A terminal automatically outputs the live **QuSec Quantum Security Report**.

### Running Dual-Mode Commands

#### Across Two Physical Laptops (Connected via Wi-Fi / LAN / Optical Transceivers):
```bash
# On Laptop A (e.g. IP 192.168.1.10):
qusec bridge --peer-host 192.168.1.20 --role dual --backend 1

# On Laptop B (e.g. IP 192.168.1.20):
qusec bridge --peer-host 192.168.1.10 --role dual --backend 1
```

#### On a Single Laptop (Simulation Testing via 2 Terminals):
```bash
# Terminal 1 (Peer A - Gateway Port 8765, Optical 9876, Classical 9877):
qusec bridge --peer a --backend 1

# Terminal 2 (Peer B - Gateway Port 8766, Optical 9878, Classical 9879):
qusec bridge --peer b --backend 1
```

---

## ⚛️ 3 Quantum Execution Backends

QuSec supports 3 selectable quantum execution backends via the `--backend` flag (`1`, `2`, `3`, or named aliases):

| Option | CLI Flag | Backend Name | Description | Error Profile |
|:---:|:---:|:---|:---|:---|
| **1** | `--backend 1` or `--backend aer` | **AerSimulator** | Ideal local quantum statevector / matrix simulation via Qiskit Aer. | $Q_0 = 0.00\%$ |
| **2** | `--backend 2` or `--backend noisy` | **Noisy AerSimulator** | Calibrated optical fiber depolarizing noise model ($0.3\%$ 1-qubit gate error, $0.4\%$ 2-qubit CX gate error, thermal relaxation). | $Q_0 \approx 1.00\%$ |
| **3** | `--backend 3` or `--backend hardware` | **Quantum Hardware** | Real physical superconducting quantum processor on IBM Quantum Cloud via `qiskit-ibm-runtime` (e.g., `ibm_kyoto`). | Live QPU Calibration |

### Setting Up IBM Quantum Hardware (Backend 3)
```bash
# Provide token via command line:
qusec bridge --role dual --backend 3 --ibm-token YOUR_IBM_QUANTUM_API_TOKEN

# Or export environment variable:
export IBM_QUANTUM_TOKEN="YOUR_IBM_QUANTUM_API_TOKEN"
qusec bridge --role dual --backend 3
```
*Note: If no IBM Quantum token is configured or the cloud is unreachable, QuSec automatically falls back to AerSimulator with a console advisory.*

---

## 📐 Mathematical Foundations

QuSec's threat decisions, error corrections, and thresholds are strictly derived from peer-reviewed quantum information theory.

### 1. Mathematical Auto-Adjusting QBER Threshold ($Q_{\text{th\_dyn}}$)
Rather than using an arbitrary static threshold, QuSec computes an adaptive dynamic threshold based on message sample size $n$, real-time channel traffic rate $\Phi$, and slow thermal drift $\bar{Q}_{\text{ema}}$:

$$Q_{\text{th\_dyn}}(n, \Phi) = \min\left(Q_{\text{ceiling}}, \; \max\left(Q_{\text{floor}}, \; \bar{Q}_{\text{ema}} + \Delta_{\text{traffic}}(\Phi) + \Delta_{\text{stat}}(n)\right)\right)$$

#### A. Spontaneous Raman Scattering (SpRS) Traffic Penalty $\Delta_{\text{traffic}}(\Phi)$
Co-propagating classical frames across adjacent wavelengths or co-routed fiber bundles introduce SpRS noise photons into the single-photon quantum channel (*Patel et al., Phys. Rev. X 2012*):

$$\Delta_{\text{traffic}}(\Phi) = \alpha_{\text{traffic}} \cdot \ln\left(1 + \frac{\Phi}{\Phi_{\text{ref}}}\right)$$

- $\Phi$: Real-time transmission traffic rate (messages/second) tracked over a 10-second sliding window.
- $\alpha_{\text{traffic}} = 0.012$ (calibrated Raman coupling coefficient).
- $\Phi_{\text{ref}} = 1.0\text{ msg/sec}$.

#### B. Finite-Size Hoeffding Statistical Bound $\Delta_{\text{stat}}(n)$
For short messages (finite key regime), statistical fluctuations are wider. QuSec bounds finite-size deviations using Hoeffding's concentration inequality (*Tomamichel et al., Nat. Commun. 2012*):

$$\Delta_{\text{stat}}(n) = \beta_{\text{stat}} \cdot \sqrt{\frac{\ln(2/\delta)}{2n}}$$

- $n$: Number of conclusive sifted test/decoy qubits ($\mu$ state).
- $\delta = 10^{-3}$: Security failure probability ($1 - \delta = 99.9\%$ confidence level).
- $\beta_{\text{stat}} = 0.28$: Finite-sample weighting factor.

#### C. Asymptotic Security Ceiling ($Q_{\text{ceiling}} = 11.0\%$)
According to the Shor-Preskill unconditional security bound (*Scarani et al., Rev. Mod. Phys. 2009*), the secret key rate $R$ drops to zero when $QBER > 11.0\%$:

$$R \ge 1 - 2 H_2(QBER) \quad \Longrightarrow \quad R = 0 \text{ at } QBER \approx 11.0\%$$

Beyond $11.0\%$, the mutual information between Alice and Bob $I(A:B)$ is strictly less than Eve's information $I(A:E)$. Thus, $Q_{\text{th\_dyn}}$ is capped at $0.110$.

#### D. Slow Optical Channel Drift ($\bar{Q}_{\text{ema}}$)
Slow mechanical strain and thermal drift of the glass fiber are tracked using an Exponential Moving Average (EMA) on verified transmissions:

$$\bar{Q}_{\text{ema}}^{(k)} = \lambda \bar{Q}_{\text{ema}}^{(k-1)} + (1 - \lambda) Q_{\text{meas}}^{(k)} \quad (\lambda = 0.85)$$

### 2. Quantum State Teleportation & Pauli Corrections
QuSec teleports quantum states using 3-qubit Bell entanglement $|\Phi^+\rangle = \frac{1}{\sqrt{2}}(|00\rangle + |11\rangle)$ (*Bennett et al., PRL 1993*). After Alice's Bell State Measurement (BSM), Bob's qubit is transformed to:

$$|\psi_{\text{Bob}}\rangle = X^{c_1} Z^{c_0} |\psi_{\text{Alice}}\rangle$$

Bob applies conditional Pauli corrections over the classical channel:
- If $c_1 = 1$, Bob executes Pauli $X$ (bit-flip correction).
- If $c_0 = 1$, Bob executes Pauli $Z$ (phase-flip correction).

### 3. SARG04 Decoy-State Verification
To detect photon number splitting (PNS) attacks, QuSec modulates pulse intensities:
- **$\mu$ state (signal)**: Conclusive sifting with non-orthogonal state pairs.
- **$\nu$ state (weak decoy)**: Validates single-photon yield $Y_1$.
- **Vacuum state (dark)**: Directly measures detector dark count rate $Y_0$.

---

## 📚 Research Papers & Academic References

The theoretical models, security thresholds, and protocols implemented in QuSec are based on the following scientific publications:

1. **Patel, K. A., Dynes, J. F., Choi, I., Sharpe, A. W., Dixon, A. R., Yuan, Z. L., Penty, R. V., & Shields, A. J.** (2012).  
   *Coexistence of high-bit-rate quantum key distribution and data on optical fiber*.  
   **Physical Review X**, 2(4), 041010.  
   DOI: [10.1103/PhysRevX.2.041010](https://doi.org/10.1103/PhysRevX.2.041010)  
   *(Provides the mathematical foundation for QuSec's Spontaneous Raman Scattering traffic noise scaling $\Delta_{\text{traffic}}$).*

2. **Eraerds, P., Walenta, N., Legré, M., Gisin, N., & Zbinden, H.** (2010).  
   *Quantum key distribution and 1 Gbps data coexistence in a single fiber*.  
   **New Journal of Physics**, 12(6), 063027.  
   DOI: [10.1088/1367-2630/12/6/063027](https://doi.org/10.1088/1367-2630/12/6/063027)

3. **Tomamichel, M., Lim, C. C. W., Gisin, N., & Renner, R.** (2012).  
   *Tight finite-key analysis for quantum cryptography*.  
   **Nature Communications**, 3, 634.  
   DOI: [10.1038/ncomms1631](https://doi.org/10.1038/ncomms1631)  
   *(Provides the composable finite-key Hoeffding concentration bounds implemented in QuSec).*

4. **Scarani, V., Bechmann-Pasquinucci, H., Cerf, N. J., Dušek, M., Lütkenhaus, N., & Peev, M.** (2009).  
   *The security of practical quantum key distribution*.  
   **Reviews of Modern Physics**, 81(3), 1301–1350.  
   DOI: [10.1103/RevModPhys.81.1301](https://doi.org/10.1103/RevModPhys.81.1301)  
   *(Establishes the asymptotic $11.0\%$ QBER ceiling and security proof bounds).*

5. **Bennett, C. H., Brassard, G., Crépeau, C., Jozsa, R., Peres, A., & Wootters, W. K.** (1993).  
   *Teleporting an unknown quantum state via dual classical and Einstein-Podolsky-Rosen channels*.  
   **Physical Review Letters**, 70(13), 1895–1899.  
   DOI: [10.1103/PhysRevLett.70.1895](https://doi.org/10.1103/PhysRevLett.70.1895)  
   *(Foundational protocol for QuSec's 3-qubit Bell state measurement and Pauli $X/Z$ corrections).*

6. **Gottesman, D., & Chuang, I. L.** (2001).  
   *Quantum digital signatures*.  
   **arXiv preprint quant-ph/0105032**.  
   arXiv: [quant-ph/0105032](https://arxiv.org/abs/quant-ph/0105032)  
   *(Theoretical basis for non-repudiation and quantum asymmetric signature verification).*

7. **Shor, P. W., & Preskill, J.** (2000).  
   *Simple proof of security of the BB84 quantum key distribution protocol*.  
   **Physical Review Letters**, 85(2), 441–444.  
   DOI: [10.1103/PhysRevLett.85.441](https://doi.org/10.1103/PhysRevLett.85.441)

8. **Wegman, M. N., & Carter, J. L.** (1981).  
   *New hash functions and their use in authentication and set equality*.  
   **Journal of Computer and System Sciences**, 22(3), 265–279.  
   DOI: [10.1016/0022-0000(81)90033-7](https://doi.org/10.1016/0022-0000(81)90033-7)  
   *(Basis for QuSec's key-pool-based classical packet authentication tags).*

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

QuSec comes with an interactive Terminal User Interface (TUI). To launch the framework and start a secure simulation transfer:
```bash
qusec run
```

### Advanced Usage Flags
- **Select execution backend:**
  ```bash
  qusec run --backend 1      # AerSimulator (ideal)
  qusec run --backend 2      # Noisy AerSimulator
  qusec run --backend 3      # IBM Quantum Hardware
  ```
- **Simulate attack vectors directly:**
  ```bash
  qusec run --attack tampering
  qusec run --attack forgery
  ```
- **Machine-readable JSON output:**
  ```bash
  qusec run --json
  ```

---

## 🌐 Real-World Hardware & Transport Architecture

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

---

## 🛠️ CLI Commands

### 1. Link Diagnostics (`qusec doctor`)
```bash
qusec doctor
qusec doctor --peer-host 192.168.2.2
```

### 2. Website & Platform Bridge Monitor (`qusec bridge`)
Connects the terminal directly to the [Shnik Web App](https://shnik-lake.vercel.app), ESP32 classical channel, and optical quantum channel in **Live Transmission Monitor** mode:
```bash
# Dual-mode transmission across two laptops:
qusec bridge --peer-host <PEER_IP> --role dual --backend 1

# Simulation test on single machine:
qusec bridge --peer a --backend 1
qusec bridge --peer b --backend 1
```

### 3. Continuous Interactive Quantum Chat (`qusec chat`)
```bash
qusec chat --role dual --peer-host <PEER_IP> --backend 1
```

### 4. Interactive Node & Live UI Dashboard (`qusec node`)
```bash
qusec node --role dual --peer-host <PEER_IP> --backend 1
```

### 5. Social Media Platform Bridge Gateway (`qusec gateway`)
```bash
qusec gateway --role dual --port 8765 --backend 1
```

### 6. Key Pool Inspector (`qusec keys`)
```bash
qusec keys
```

### 7. Quantum-Secure Send (`qusec send`)
```bash
qusec send "Hello Quantum Teleportation" --to receiver --mode teleportation --backend 1
qusec send "Top Secret" --to receiver --mode otp
```

### 8. QuSec Attacker & Claude Code TUI Adversary (`qusec attacker`)
Run the adversary console (Eve) on the 3rd laptop connected to the Attacker ESP32:
```bash
# Interactive Claude Code TUI session:
qusec attacker --target-host <RECEIVER_IP>

# Direct attack vector (non-interactive):
qusec attacker --sim --attack tamper --rate 0.35

# Dedicated standalone executable:
qusec-attacker --random
```
Interactive Slash Commands in Attacker TUI:
- `/attack <qber|tamper|forgery|replay|jam>` — Launch targeted disturbance or corruption
- `/random <on|off> [min_sec] [max_sec]` — Automated random in-between chat attack mode
- `/mitm <start|stop>` — Transparent hardware/socket proxy with live packet sniffing
- `/target <ip> [classical_port] [optical_port]` — Set target laptop coordinates
- `/stats` — Display injected packets and active telemetry
- `/help` — View adversary manual

---

## ⚡ ESP32 Firmware

### 1. Classical Relay & Endpoint Firmware
Provided in: `firmware/esp32_qusec/esp32_qusec.ino`
- True Hardware RNG via `esp_random()`
- Wi-Fi Access Point / Station Classical Relay (Port `9877`)
- Threat Alarm LED Driver on GPIO 4
- Serial protocol interface at `115200` baud

### 2. Attacker ESP32 Firmware (Eve)
Provided in: `firmware/esp32_attacker/esp32_attacker.ino`
- True Hardware RNG via `esp_random()` (`RNG <bytes>`)
- Promiscuous Mode Wi-Fi Packet Sniffer (`SNIFF 1/0`)
- Raw Frame Injection across classical & optical networks (`TX <hex>`)
- High-frequency RF/UDP Jamming bursts (`JAM <count> <delay>`)
- Attack Blast LED on GPIO 4 (`ALARM 1/0 [blink_ms]`)

