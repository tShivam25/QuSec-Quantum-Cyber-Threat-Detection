"""
QuSec Hardware Subsystem: ESP32 auto-detection, True RNG, Optical Ethernet transceiver channel,
and Classical wireless channel drivers.
"""

from qusec.hardware.esp32 import ESP32Device, ESP32Detector
from qusec.hardware.rng import RandomSource
from qusec.hardware.optical import QuantumChannel, EthernetDetector
from qusec.hardware.classical import ClassicalChannel
from qusec.hardware.doctor import run_doctor

__all__ = [
    "ESP32Device",
    "ESP32Detector",
    "RandomSource",
    "QuantumChannel",
    "EthernetDetector",
    "ClassicalChannel",
    "run_doctor",
]
