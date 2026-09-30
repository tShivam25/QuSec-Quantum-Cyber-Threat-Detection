# QuSec - Quantum Security Framework

## Description
QuSec is a comprehensive Quantum Security Framework designed for Quantum Digital Signature (QDS) threat detection.

## Introduction
It leverages Qiskit to simulate a quantum-safe teleportation-based QDS protocol layered with the SARG04 decoy-state method to detect active tampering, forgery, and interception attacks.

## PyPI Link
[QuSec on PyPI](https://pypi.org/project/qusec/)

## 🚀 Features

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

## 🏗️ Architecture

```text
                    QUSEC SECURITY ENGINE
                           │
                  Quantum Circuit Layer
                           │
                 Abstract Backend Manager
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
      AerSimulator    Noisy AerSimulator   Quantum Hardware
                           │
                  Measurement Results
                           │
               Projective/SARG04 Security Pipeline
```


