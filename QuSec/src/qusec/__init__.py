"""
QuSec - Quantum Security Framework for Quantum Digital Signature Threat Detection
"""

__version__ = "0.2.11"
from qusec.quantum.bell import bell_pair, correct
from qusec.detection.qber import qber, hoeffding_margin, theoretical_qber, TwoBasisQBEREstimator
from qusec.detection.threshold import ThresholdEngine, DynamicThresholdEngine
from qusec.qds.signature import QuantumDigitalSignature
from qusec.node import QuSecNode
from qusec.hardware.optical import QuantumChannel
from qusec.hardware.classical import ClassicalChannel
from qusec.hardware.rng import RandomSource
from qusec.hardware.doctor import run_doctor
from qusec.session.key_pool import KeyPool
from qusec.session.manager import SessionManager
from qusec.quantum.backend import get_backend, get_backend_label, normalize_backend_type
from qusec.quantum.entanglement import EntanglementEngine
from qusec.quantum.teleport import QuantumTeleportationEngine
from qusec.crypto.quantum_keys import QuantumKeyPair, QuantumPublicKey, QuantumPrivateKey
from qusec.attacker import QuSecAttacker, AttackerESP32Device

__all__ = [
    "bell_pair",
    "correct",
    "qber",
    "hoeffding_margin",
    "theoretical_qber",
    "TwoBasisQBEREstimator",
    "ThresholdEngine",
    "DynamicThresholdEngine",
    "QuantumDigitalSignature",
    "QuSecNode",
    "QuSecAttacker",
    "AttackerESP32Device",
    "QuantumChannel",
    "ClassicalChannel",
    "RandomSource",
    "KeyPool",
    "SessionManager",
    "get_backend",
    "get_backend_label",
    "normalize_backend_type",
    "EntanglementEngine",
    "QuantumTeleportationEngine",
    "OneTimePad",
    "QuantumKeyPair",
    "QuantumPublicKey",
    "QuantumPrivateKey",
    "run_doctor",
    "__version__",
]
