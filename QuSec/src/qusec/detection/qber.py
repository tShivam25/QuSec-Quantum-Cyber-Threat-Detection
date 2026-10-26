"""
Mathematical Quantum Bit Error Rate (QBER) estimation from Pauli correlators,
Hoeffding-bounded confidence intervals, and theoretical models as defined in:
'QuSec: Cyber Threat Detection in Quantum Communication Channel' (Section III-F, VII).
"""

import math
from typing import Sequence, Tuple, Dict, Any

def qber(a: Sequence[int], b: Sequence[int]) -> float:
    """
    Standard sifted bit error rate.
    Paper Eq. (12) & Section VII:
        Q = Nerr / Nsift = (1 / Nsift) * sum(ai ^ bi)
        return sum(x != y for x, y in zip(a, b)) / len(a)
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x != y for x, y in zip(a, b)) / len(a)

def qber_from_correlator(correlator: float) -> float:
    """
    Computes QBER from Pauli correlator <P (x) P> for Bell pairs.
    Paper Eq. (13):
        QP = (1 - <P (x) P>) / 2
    """
    c = max(-1.0, min(1.0, correlator))
    return (1.0 - c) / 2.0

def hoeffding_margin(n: int, delta: float = 0.001) -> float:
    """
    Computes the finite-size confidence margin epsilon(n, delta) using Hoeffding's inequality.
    Paper Eq. (15):
        Pr[|Q_hat - Q| >= epsilon] <= 2 * exp(-2 * n * epsilon^2)
        epsilon(n, delta) = sqrt(ln(2 / delta) / (2 * n))
    Guarantees Q <= Q_hat + epsilon with confidence 1 - delta.
    For n = 10^4 and delta = 10^-3, epsilon approx 1.95%.
    """
    if n <= 0 or delta <= 0 or delta >= 1.0:
        return 0.0
    return math.sqrt(math.log(2.0 / delta) / (2.0 * n))

def theoretical_qber(attack_type: str, param: float = 0.0, baseline_q0: float = 0.01) -> float:
    """
    Computes the exact theoretical QBER for given attack scenario.
    Paper Table II, Table III & Section VII:
        Q = Q0 + (1 - 2 * Q0) * Q_attack
        - Ideal, no noise: Q = 0.0
        - Baseline, no attack: Q = Q0 (default 1.0%)
        - Intercept-Resend (Eq. 14): Q_IR = mu / 4
        - Depolarising noise (Eq. 11): Q_depol = p / 2
        - Replay attack (Section VI-C): Q_replay = 0.50 (50%)
        - Impersonation (Section VI-B): Q_imp = 0.50 (50%)
    """
    if attack_type == 'ideal':
        return 0.0
    elif attack_type in (None, 'none', 'no_attack'):
        return baseline_q0
    elif attack_type == 'intercept_resend':
        q_attack = param / 4.0
    elif attack_type == 'depolarizing':
        q_attack = param / 2.0
    elif attack_type in ('replay', 'impersonation'):
        q_attack = 0.50
    elif attack_type == 'disturbance':
        q_attack = (math.sin(param / 2.0) ** 2) if param > 0 else 0.25
    elif attack_type == 'forgery':
        q_attack = 0.40
    else:
        q_attack = param

    return baseline_q0 + (1.0 - 2.0 * baseline_q0) * q_attack

class TwoBasisQBEREstimator:
    """
    Estimates QBER in both Z (bit-flip) and X (phase-flip) bases separately.
    Paper Section III-E, III-F, IV:
        QZ = px + py, QX = pz + py
        Measuring both bases exposes asymmetric disturbance that a single-basis test misses.
    """
    def __init__(self, delta: float = 0.001):
        self.delta = delta
        self.z_rounds = 0
        self.z_errors = 0
        self.x_rounds = 0
        self.x_errors = 0

    def record_measurement(self, basis: str, sent_bit: int, received_bit: int):
        is_err = (sent_bit != received_bit)
        if basis == 'Z':
            self.z_rounds += 1
            if is_err:
                self.z_errors += 1
        elif basis == 'X':
            self.x_rounds += 1
            if is_err:
                self.x_errors += 1

    def get_estimates(self) -> Dict[str, Any]:
        qz = (self.z_errors / self.z_rounds) if self.z_rounds > 0 else 0.0
        qx = (self.x_errors / self.x_rounds) if self.x_rounds > 0 else 0.0
        total_n = self.z_rounds + self.x_rounds
        total_errors = self.z_errors + self.x_errors
        q_avg = (total_errors / total_n) if total_n > 0 else 0.0
        eps = hoeffding_margin(total_n, self.delta) if total_n > 0 else 0.0
        
        return {
            "Q_Z": qz,
            "Q_X": qx,
            "Q_avg": q_avg,
            "max_Q": max(qz, qx),
            "epsilon": eps,
            "Q_upper_bound": max(qz, qx) + eps,
            "sample_size": total_n,
            "z_rounds": self.z_rounds,
            "x_rounds": self.x_rounds
        }
