"""
Cascade Interactive Error Correction Protocol for QuSec.
Performs multi-pass parity checking and binary bisection search over the authenticated
classical channel to reconcile bit discrepancies between Alice and Bob's sifted keys.
"""

import math
import random
from typing import List, Tuple, Dict, Any


class CascadeReconciler:
    """
    Implements the Cascade error-correction algorithm:
    - Pass 1: Divides key into blocks of size k1, checks parity. Mismatched blocks are bisected.
    - Subsequent passes: Randomly permute key with known seed, double block size, repeat.
    """

    def __init__(self, target_qber: float = 0.02, num_passes: int = 4):
        self.target_qber = max(0.001, target_qber)
        self.num_passes = num_passes

    def _initial_block_size(self) -> int:
        """Heuristic block size k1 approx 0.73 / QBER."""
        k = int(0.73 / self.target_qber)
        return max(4, min(128, k))

    @staticmethod
    def _compute_parity(bits: List[int]) -> int:
        """Parity = sum(bits) % 2."""
        return sum(bits) & 1

    def reconcile(
        self,
        alice_bits: List[int],
        bob_bits: List[int],
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Reconcile Bob's sifted bits to match Alice's bits.
        Returns the reconciled bits, number of corrected errors, and total leaked parity bits.
        """
        if len(alice_bits) != len(bob_bits):
            raise ValueError("Key lengths must match for Cascade reconciliation")

        n = len(alice_bits)
        if n == 0:
            return {"reconciled_bob": [], "corrected_errors": 0, "leaked_bits": 0, "residual_errors": 0}

        bob_current = list(bob_bits)
        total_corrected = 0
        total_leaked_parity = 0
        k = self._initial_block_size()

        rng = random.Random(seed)

        for pass_num in range(1, self.num_passes + 1):
            # Generate permutation for this pass
            perm = list(range(n))
            if pass_num > 1:
                rng.shuffle(perm)

            inv_perm = [0] * n
            for i, p in enumerate(perm):
                inv_perm[p] = i

            permuted_alice = [alice_bits[p] for p in perm]
            permuted_bob = [bob_current[p] for p in perm]

            # Process blocks
            block_size = k * (2 ** (pass_num - 1))
            num_blocks = (n + block_size - 1) // block_size

            for b in range(num_blocks):
                start = b * block_size
                end = min(n, start + block_size)
                if start >= end:
                    continue

                sub_a = permuted_alice[start:end]
                sub_b = permuted_bob[start:end]

                p_a = self._compute_parity(sub_a)
                p_b = self._compute_parity(sub_b)
                total_leaked_parity += 1  # Alice reveals 1 parity bit

                if p_a != p_b:
                    # Odd number of errors in this block -> binary search to find an error
                    err_offset, leak = self._binary_search_error(sub_a, sub_b)
                    total_leaked_parity += leak
                    err_idx = start + err_offset

                    # Flip erroneous bit in Bob's permuted array
                    permuted_bob[err_idx] = 1 - permuted_bob[err_idx]
                    total_corrected += 1

            # Un-permute Bob's bits
            bob_current = [permuted_bob[inv_perm[i]] for i in range(n)]

        residual = sum(1 for a, b in zip(alice_bits, bob_current) if a != b)

        return {
            "reconciled_bob": bob_current,
            "corrected_errors": total_corrected,
            "leaked_bits": total_leaked_parity,
            "residual_errors": residual,
            "success": residual == 0,
        }

    def _binary_search_error(self, sub_a: List[int], sub_b: List[int]) -> Tuple[int, int]:
        """Bisect block to find index of bit flip."""
        start = 0
        end = len(sub_a)
        leaked = 0

        while end - start > 1:
            mid = (start + end) // 2
            p_a = self._compute_parity(sub_a[start:mid])
            p_b = self._compute_parity(sub_b[start:mid])
            leaked += 1

            if p_a != p_b:
                end = mid
            else:
                start = mid

        return start, leaked
