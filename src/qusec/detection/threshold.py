"""
Threshold Engine for QuSec Protocol.
Implements security threshold evaluation for QBER and signature verification:
- Channel security threshold (Q_th): Default 0.06 (6.00%)
- Signature acceptance threshold (sa): Default 0.05 (5.00%)
- Signature verification threshold (sv): Default 0.15 (15.00%)
Guarantees transferability and non-repudiation as defined in Paper Eq. (18).
"""

from typing import Dict, Any


class ThresholdEngine:
    """
    Evaluates quantum channel QBER and two-threshold signature acceptance/verification.
    """

    def __init__(self, sa: float = 0.05, sv: float = 0.15, q_threshold: float = 0.06):
        self.sa = sa
        self.sv = sv
        self.q_threshold = q_threshold

    def evaluate_signature(self, mismatch_rate: float) -> Dict[str, Any]:
        """
        Evaluate signature mismatch rate against two-threshold bounds (Eq. 18).
        - m <= sa: VALID (Recipient accepts and transfer is guaranteed)
        - sa < m <= sv: TRANSFERABLE (Recipient rejects, but transferable to verifier)
        - m > sv: FORGED (Rejected by all parties)
        """
        if mismatch_rate <= self.sa:
            return {
                "verdict": "VALID",
                "is_valid": True,
                "is_transferable": True,
                "mismatch": mismatch_rate,
                "threshold": self.sa
            }
        elif mismatch_rate <= self.sv:
            return {
                "verdict": "TRANSFERABLE",
                "is_valid": False,
                "is_transferable": True,
                "mismatch": mismatch_rate,
                "threshold": self.sv
            }
        else:
            return {
                "verdict": "FORGED",
                "is_valid": False,
                "is_transferable": False,
                "mismatch": mismatch_rate,
                "threshold": self.sv
            }

    def evaluate_channel(self, calculated_qber: float) -> Dict[str, Any]:
        """
        Evaluate calculated QBER against channel security threshold Q_th.
        """
        exceeded = calculated_qber > self.q_threshold
        status = "EXCEEDED (Threat Detected)" if exceeded else "NORMAL (Within Tolerance)"
        return {
            "qber": calculated_qber,
            "threshold": self.q_threshold,
            "exceeded": exceeded,
            "status": status,
            "decision": "THREAT DETECTED" if exceeded else "VERIFIED"
        }
