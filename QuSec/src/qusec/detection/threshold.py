"""
Dynamic & Auto-Adjusting Threshold Engine for QuSec.
Implements mathematically rigorous, adaptive QBER threshold evaluation based on:
1. Baseline physical optical misalignment and detector dark count noise (Q0).
2. Real-time classical & quantum channel traffic rate (Phi, messages/sec) and
   Spontaneous Raman Scattering (SpRS) noise elevation:
   - Patel et al., Physical Review X 2, 041010 (2012)
   - Eraerds et al., New Journal of Physics 12, 063027 (2010)
3. Finite-sample statistical fluctuation bounds via Hoeffding's Inequality and Chernoff margins:
   - Tomamichel et al., Nature Communications 3, 634 (2012)
   - Scarani et al., Reviews of Modern Physics 81, 1301 (2009)
4. Historical channel exponential moving average (EMA) tracking thermal and mechanical drift.
5. Absolute security boundary ceiling Q_ceiling = 0.110 (11.00%), beyond which mutual
   information with an eavesdropper collapses unconditional security (Shor-Preskill / SARG04 bound).
"""

import math
import time
from typing import Dict, Any, Optional, List, Tuple


class DynamicThresholdEngine:
    """
    Mathematical Auto-Adjusting QBER Threshold Engine.
    Dynamically adjusts Q_th for varying message lengths, traffic rates, and channel drift.
    """

    def __init__(
        self,
        baseline_q0: float = 0.010,
        alpha_traffic: float = 0.012,
        traffic_ref: float = 1.0,
        beta_stat: float = 0.28,
        security_delta: float = 0.001,
        q_floor: float = 0.035,
        q_ceiling: float = 0.110,
        ema_weight: float = 0.85,
        sa: float = 0.05,
        sv: float = 0.15,
        window_seconds: float = 10.0,
        **kwargs,
    ):
        self.baseline_q0 = baseline_q0
        self.alpha_traffic = alpha_traffic
        self.traffic_ref = traffic_ref
        self.beta_stat = beta_stat
        self.security_delta = kwargs.get("confidence_delta", security_delta)
        self.q_floor = kwargs.get("min_qber_floor", q_floor)
        self.q_ceiling = kwargs.get("max_qber_ceiling", q_ceiling)
        self.ema_weight = ema_weight
        self.sa = sa
        self.sv = sv

        # Dynamic state
        self.channel_ema = baseline_q0
        self._transmission_timestamps: List[float] = []
        self._traffic_window_seconds = window_seconds
        self.last_dynamic_metrics: Dict[str, Any] = {}

    def record_transmission(self, byte_count: int = 0):
        """Record an outgoing or incoming transmission timestamp for traffic rate estimation."""
        now = time.time()
        self._transmission_timestamps.append(now)
        # Purge timestamps outside sliding window
        cutoff = now - self._traffic_window_seconds
        self._transmission_timestamps = [t for t in self._transmission_timestamps if t >= cutoff]

    def get_traffic_rate(self) -> float:
        """
        Compute current traffic rate Phi in messages/second over sliding window.
        """
        now = time.time()
        cutoff = now - self._traffic_window_seconds
        self._transmission_timestamps = [t for t in self._transmission_timestamps if t >= cutoff]
        count = len(self._transmission_timestamps)
        return count / self._traffic_window_seconds

    def compute_dynamic_threshold(
        self,
        sample_size: int = 32,
        message_length: int = 0,
        forced_traffic_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculates the exact mathematical auto-adjusted QBER threshold:
        Q_th_dyn = min(Q_ceiling, max(Q_floor, Q_ema + Delta_traffic(Phi) + Delta_stat(n)))

        Formulas:
        1. Delta_traffic(Phi) = alpha_traffic * ln(1 + Phi / Phi_ref)
           [Raman scattering noise model from Patel et al. PRX 2012]
        2. Delta_stat(n) = beta_stat * sqrt(ln(2 / delta) / (2 * n))
           [Finite-size Hoeffding confidence margin from Tomamichel et al. 2012]
        """
        n = max(16, sample_size)
        phi = forced_traffic_rate if forced_traffic_rate is not None else self.get_traffic_rate()

        # 1. Traffic penalty from co-propagating classical noise
        delta_traffic = self.alpha_traffic * math.log(1.0 + max(0.0, phi) / self.traffic_ref)

        # 2. Finite-size statistical fluctuation bound
        hoeffding_eps = math.sqrt(math.log(2.0 / self.security_delta) / (2.0 * n))
        delta_stat = self.beta_stat * hoeffding_eps

        # 3. Composite dynamic threshold
        raw_dyn = self.channel_ema + delta_traffic + delta_stat
        q_dyn = max(self.q_floor, min(self.q_ceiling, raw_dyn))

        metrics = {
            "q_dyn": q_dyn,
            "q_floor": self.q_floor,
            "q_ceiling": self.q_ceiling,
            "channel_ema": self.channel_ema,
            "baseline_q0": self.baseline_q0,
            "traffic_rate_phi": phi,
            "delta_traffic": delta_traffic,
            "sample_size_n": n,
            "message_length": message_length,
            "hoeffding_eps": hoeffding_eps,
            "delta_stat": delta_stat,
            "confidence_level": 1.0 - self.security_delta,
            "formula": "Q_th(n, Phi) = min(0.110, max(0.035, Q_ema + Delta_traffic(Phi) + Delta_stat(n)))",
        }
        self.last_dynamic_metrics = metrics
        return metrics

    def evaluate_channel(
        self,
        calculated_qber: float,
        sample_size: int = 32,
        message_length: int = 0,
        forced_traffic_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates calculated QBER against the mathematically computed dynamic threshold.
        """
        self.record_transmission()
        metrics = self.compute_dynamic_threshold(sample_size, message_length, forced_traffic_rate)
        q_dyn = metrics["q_dyn"]

        exceeded = calculated_qber > q_dyn
        status = "EXCEEDED (Threat Detected: Channel Tampering)" if exceeded else "NORMAL (Within Dynamic Tolerance)"
        decision = "THREAT DETECTED" if exceeded else "VERIFIED"

        # Update historical channel EMA on verified honest transmissions
        if not exceeded:
            self.channel_ema = self.ema_weight * self.channel_ema + (1.0 - self.ema_weight) * calculated_qber

        return {
            "qber": calculated_qber,
            "threshold": q_dyn,
            "exceeded": exceeded,
            "status": status,
            "decision": decision,
            "dynamic_metrics": metrics,
        }

    def compute_threshold(
        self,
        sample_size_n: int = 32,
        traffic_rate_phi: Optional[float] = None,
        message_length: int = 0,
    ) -> Tuple[float, Dict[str, Any]]:
        """Convenience alias returning (threshold, metrics_dict)."""
        metrics = self.compute_dynamic_threshold(
            sample_size=sample_size_n,
            message_length=message_length,
            forced_traffic_rate=traffic_rate_phi,
        )
        return metrics["q_dyn"], metrics

    def evaluate_channel_security(
        self,
        measured_qber: float,
        sample_size_n: int = 32,
        message_length: int = 0,
        traffic_rate_phi: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Convenience alias for evaluate_channel returning formatted security verdict."""
        res = self.evaluate_channel(
            calculated_qber=measured_qber,
            sample_size=sample_size_n,
            message_length=message_length,
            forced_traffic_rate=traffic_rate_phi,
        )
        return {
            "status": "THREAT DETECTED" if res["exceeded"] else "SECURE",
            "decision": res["decision"],
            "attack_detected": res["exceeded"],
            "qber": res["qber"],
            "threshold": res["threshold"],
            "proof": res["dynamic_metrics"],
        }

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
                "threshold": self.sa,
            }
        elif mismatch_rate <= self.sv:
            return {
                "verdict": "TRANSFERABLE",
                "is_valid": False,
                "is_transferable": True,
                "mismatch": mismatch_rate,
                "threshold": self.sv,
            }
        else:
            return {
                "verdict": "FORGED",
                "is_valid": False,
                "is_transferable": False,
                "mismatch": mismatch_rate,
                "threshold": self.sv,
            }

    @property
    def q_threshold(self) -> float:
        """Returns the current dynamic auto-adjusted threshold."""
        if self.last_dynamic_metrics:
            return self.last_dynamic_metrics.get("q_dyn", 0.06)
        return self.compute_dynamic_threshold()["q_dyn"]


class ThresholdEngine(DynamicThresholdEngine):
    """
    Backward-compatible alias for DynamicThresholdEngine.
    Defaults to dynamic thresholding while supporting static Q_th configuration.
    """

    def __init__(self, sa: float = 0.05, sv: float = 0.15, q_threshold: Optional[float] = None):
        super().__init__(sa=sa, sv=sv)
        self._static_threshold = q_threshold
        if q_threshold is not None:
            self.q_floor = min(self.q_floor, q_threshold)
            self.q_ceiling = max(self.q_ceiling, q_threshold)
            self.channel_ema = q_threshold

    def evaluate_channel(
        self,
        calculated_qber: float,
        sample_size: int = 32,
        message_length: int = 0,
        forced_traffic_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        return super().evaluate_channel(
            calculated_qber=calculated_qber,
            sample_size=sample_size,
            message_length=message_length,
            forced_traffic_rate=forced_traffic_rate,
        )
