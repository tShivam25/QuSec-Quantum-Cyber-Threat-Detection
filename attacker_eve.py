#!/usr/bin/env python3
"""
QuSec Attacker Executable Entry Point (Eve - 3rd Laptop)
========================================================
Runs the QuSec Adversary CLI on the 3rd laptop.
Tampers with in-transit frames between Laptop A (Alice) and Laptop B (Bob)
and triggers dynamic QBER security threshold alerts and physical ESP32 alarm LEDs.

Usage:
  Interactive Adversary TUI:
    python attacker_eve.py

  Targeting a Receiver across network:
    python attacker_eve.py --target-host 192.168.4.2 --target-classical-port 9877

  Launch directly with automated stealth attacks in-between chats:
    python attacker_eve.py --random

  Command line attack:
    python attacker_eve.py --attack tamper --rate 0.35
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))

# Add qusec-attacker library to path if running locally
attacker_src = os.path.join(current_dir, "qusec-attacker", "src")
if os.path.exists(attacker_src) and attacker_src not in sys.path:
    sys.path.insert(0, attacker_src)

# Add QuSec library to path as fallback
qusec_src = os.path.join(current_dir, "QuSec", "src")
if os.path.exists(qusec_src) and qusec_src not in sys.path:
    sys.path.insert(0, qusec_src)

try:
    from qusec_attacker.cli import main
except ImportError:
    from qusec.attacker import main

if __name__ == "__main__":
    sys.exit(main())
