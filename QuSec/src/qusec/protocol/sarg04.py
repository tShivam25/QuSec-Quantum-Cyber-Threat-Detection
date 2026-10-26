"""
SARG04 Protocol Engine with Decoy State Modulation for QuSec.
Implements 4 non-orthogonal state pairs, conclusive orthogonal discrimination,
and decoy-state photon number splitting (PNS) countermeasure.
"""

import random
from typing import Dict, Any, List, Tuple, Optional
from qusec.sarg04.protocol import generate_sarg04_candidate, sift_sarg04, get_decoy_state


class SARG04ProtocolEngine:
    """
    Executes SARG04 key distribution rounds with non-orthogonal candidate pair announcements.
    """

    def __init__(self, mu_prob: float = 0.6, nu_prob: float = 0.3, vac_prob: float = 0.1):
        self.mu_prob = mu_prob
        self.nu_prob = nu_prob
        self.vac_prob = vac_prob

    def prepare_states(self, num_qubits: int) -> Dict[str, Any]:
        """
        Alice prepares random bits and bases in {Z, X}, with decoy state tags.
        """
        bits = [random.randint(0, 1) for _ in range(num_qubits)]
        bases = [random.choice(["Z", "X"]) for _ in range(num_qubits)]
        decoys = [get_decoy_state(self.mu_prob, self.nu_prob, self.vac_prob) for _ in range(num_qubits)]
        candidates = [generate_sarg04_candidate(bits[i], bases[i]) for i in range(num_qubits)]

        return {
            "bits": bits,
            "bases": bases,
            "decoys": decoys,
            "candidates": candidates,
        }

    def measure_states(
        self,
        num_qubits: int,
        alice_bits: List[int],
        alice_bases: List[str],
        channel_error_rate: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Bob chooses random measurement bases in {Z, X} and records outcomes.
        """
        bob_bases = [random.choice(["Z", "X"]) for _ in range(num_qubits)]
        bob_outcomes = []

        for i in range(num_qubits):
            a_bit = alice_bits[i]
            a_base = alice_bases[i]
            b_base = bob_bases[i]

            if a_base == b_base:
                # Same basis: deterministic outcome, with channel noise
                out = (1 - a_bit) if random.random() < channel_error_rate else a_bit
            else:
                # Conjugate basis: 50% random outcome
                out = random.randint(0, 1)

            bob_outcomes.append(out)

        return {
            "bob_bases": bob_bases,
            "bob_outcomes": bob_outcomes,
        }

    def sift_keys(
        self,
        alice_prep: Dict[str, Any],
        bob_meas: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Perform SARG04 sifting based on candidate pair announcements.
        Bob eliminates candidates orthogonal to his measurement outcomes.
        """
        num_qubits = len(alice_prep["bits"])
        sifted_alice = []
        sifted_bob = []
        conclusive_indices = []
        errors = 0

        for i in range(num_qubits):
            # Vacuum states produce no detection
            if alice_prep["decoys"][i] == "vac":
                continue

            sent_state = (alice_prep["bits"][i], alice_prep["bases"][i])
            res = sift_sarg04(
                bob_res=bob_meas["bob_outcomes"][i],
                bob_basis=bob_meas["bob_bases"][i],
                candidate_set=alice_prep["candidates"][i],
                sent_state=sent_state,
            )

            if res["conclusive"]:
                conclusive_indices.append(i)
                sifted_alice.append(alice_prep["bits"][i])
                sifted_bob.append(res["reconstructed_bit"])
                if res["is_error"]:
                    errors += 1

        total_conclusive = len(conclusive_indices)
        qber = (errors / total_conclusive) if total_conclusive > 0 else 0.0

        return {
            "sifted_alice": sifted_alice,
            "sifted_bob": sifted_bob,
            "conclusive_count": total_conclusive,
            "error_count": errors,
            "qber": round(qber, 4),
            "yield_ratio": round(total_conclusive / num_qubits, 4) if num_qubits > 0 else 0.0,
        }
