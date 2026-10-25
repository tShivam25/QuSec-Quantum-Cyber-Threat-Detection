"""
QuSec - Quantum Security Framework for Quantum Digital Signature Threat Detection
"""

__version__ = "0.1.0"
from qusec.quantum.bell import bell_pair, correct
from qusec.detection.qber import qber, hoeffding_margin, theoretical_qber, TwoBasisQBEREstimator
from qusec.detection.threshold import ThresholdEngine
from qusec.qds.signature import QuantumDigitalSignature

__version__ = "0.1.1"

__all__ = [
    "bell_pair",
    "correct",
    "qber",
    "hoeffding_margin",
    "theoretical_qber",
    "TwoBasisQBEREstimator",
    "ThresholdEngine",
    "QuantumDigitalSignature",
    "__version__"
]
