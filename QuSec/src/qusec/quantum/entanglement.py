"""
Entanglement Engine for QuSec.
Manages Bell pair generation, distribution frames over the optical fibre channel,
test-pair sacrifice, CHSH inequality evaluation, and quantum fidelity estimation.
"""

import math
import random
from typing import Dict, Any, List, Tuple, Optional
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qusec.quantum.backend import execute_circuit
from qusec.quantum.bell import bell_pair, compute_pauli_correlator


class EntanglementEngine:
    """
    Coordinates Bell-pair creation, optical distribution framing,
    CHSH test-pair sacrifice, and entanglement verification.
    """

    def __init__(self, backend_type: str = "simulator", credentials: Optional[Dict[str, Any]] = None):
        self.backend_type = backend_type
        self.credentials = credentials

    def create_bell_pair(self) -> QuantumCircuit:
        """Create a standard maximally entangled Bell pair |Phi+>."""
        return bell_pair()

    def generate_distribution_frame(self, total_pairs: int = 512, test_ratio: float = 0.125) -> Dict[str, Any]:
        """
        Partition pairs into test pairs (for CHSH & fidelity estimation)
        and data pairs (retained for quantum teleportation / key generation).
        """
        test_count = max(4, int(total_pairs * test_ratio))
        indices = list(range(total_pairs))
        random.shuffle(indices)
        test_indices = set(indices[:test_count])

        frame = {
            "total_pairs": total_pairs,
            "test_pairs_count": test_count,
            "data_pairs_count": total_pairs - test_count,
            "test_indices": list(test_indices),
            "state_type": "Phi_plus",
        }
        return frame

    def measure_chsh_correlators(
        self,
        num_shots_per_setting: int = 250,
        depolarizing_noise: float = 0.0,
        attack_type: str = None,
    ) -> Dict[str, Any]:
        """
        Measure CHSH inequality parameter S = E(A0,B0) + E(A0,B1) + E(A1,B0) - E(A1,B1).
        Alice settings:
            A0 = 0 (Z basis)
            A1 = pi/2 (X basis)
        Bob settings:
            B0 = pi/4
            B1 = -pi/4
        Quantum mechanics predicts S = 2*sqrt(2) approx 2.828.
        Classical/intercept-resend bound is S <= 2.0.
        """
        settings = [
            ("A0", "B0", 0.0, math.pi / 4.0),
            ("A0", "B1", 0.0, -math.pi / 4.0),
            ("A1", "B0", math.pi / 2.0, math.pi / 4.0),
            ("A1", "B1", math.pi / 2.0, -math.pi / 4.0),
        ]

        correlators = {}
        eve_b = random.choice(["Z", "X"]) if attack_type == "intercept_resend" else None

        for a_name, b_name, theta_a, theta_b in settings:
            qr = QuantumRegister(2, "q")
            cr = ClassicalRegister(2, "c")
            qc = QuantumCircuit(qr, cr)

            # 1. Generate Bell pair |Phi+>
            qc.h(0)
            qc.cx(0, 1)

            # Attack or channel disturbance on transmitted qubit (q1)
            if attack_type == "intercept_resend":
                # Eve measures in consistent basis across session
                if eve_b == "X": qc.h(1)
                qc.measure(1, 1)
                if eve_b == "X": qc.h(1)
            elif attack_type == "tampering":
                qc.x(1)
            elif depolarizing_noise > 0.0 and random.random() < depolarizing_noise:
                qc.x(1)

            # 2. Measurement rotations
            # Alice rotation by theta_a around Y axis
            if theta_a != 0.0:
                qc.ry(-theta_a, 0)
            # Bob rotation by theta_b around Y axis
            if theta_b != 0.0:
                qc.ry(-theta_b, 1)

            qc.measure(0, 0)
            qc.measure(1, 1)

            counts = execute_circuit(qc, backend_type=self.backend_type, credentials=self.credentials, shots=num_shots_per_setting)
            corr = compute_pauli_correlator(counts)
            correlators[f"{a_name}_{b_name}"] = corr

        e_a0_b0 = correlators["A0_B0"]
        e_a0_b1 = correlators["A0_B1"]
        e_a1_b0 = correlators["A1_B0"]
        e_a1_b1 = correlators["A1_B1"]

        # CHSH S parameter
        s_value = abs(e_a0_b0 + e_a0_b1 + e_a1_b0 - e_a1_b1)

        # Estimate Fidelity F = (1 + <ZZ> + <XX> - <YY>)/4
        # In ideal case, S/2*sqrt(2) approximates quantum correlation
        fidelity = max(0.5, min(1.0, 0.5 + (s_value / (4.0 * math.sqrt(2.0)))))
        trusted = s_value > 2.0 and fidelity >= 0.85

        return {
            "CHSH_S": round(s_value, 3),
            "fidelity": round(fidelity, 3),
            "correlators": correlators,
            "trusted": trusted,
            "violation": s_value > 2.0,
            "quantum_bound": 2.828,
            "classical_bound": 2.0,
        }
