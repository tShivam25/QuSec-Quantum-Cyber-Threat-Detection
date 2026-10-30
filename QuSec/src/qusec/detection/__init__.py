"""
QuSec Detection Package: QBER estimation and threshold evaluation.
"""

from qusec.detection.qber import (
    qber,
    qber_from_correlator,
    hoeffding_margin,
    theoretical_qber,
    TwoBasisQBEREstimator,
)
from qusec.detection.threshold import ThresholdEngine, DynamicThresholdEngine

__all__ = [
    "qber",
    "qber_from_correlator",
    "hoeffding_margin",
    "theoretical_qber",
    "TwoBasisQBEREstimator",
    "ThresholdEngine",
    "DynamicThresholdEngine",
]
