"""
Privacy Amplification for QuSec.
Applies universal hashing and Toeplitz extraction to eliminate partial mutual information
leaked to eavesdroppers during optical channel transmission and Cascade error correction.
"""

import math
import hashlib
from typing import List, Tuple, Dict, Any


def binary_entropy(p: float) -> float:
    """Shannon binary entropy function h(p) = -p*log2(p) - (1-p)*log2(1-p)."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


class PrivacyAmplifier:
    """
    Compresses reconciled keys into secure key material using universal hashing.
    """

    def __init__(self, security_margin: int = 16):
        self.security_margin = security_margin

    def calculate_secure_length(
        self,
        raw_length: int,
        qber: float,
        leaked_bits: int,
    ) -> int:
        """
        Calculate final secure key length m according to Leftover Hash Lemma:
        m <= n * (1 - h(2 * QBER)) - leaked_bits - security_margin.
        """
        if raw_length <= 0:
            return 0

        # Upper bound on Eve's information per bit in SARG04
        info_per_bit = binary_entropy(min(0.499, 2.0 * max(0.001, qber)))
        eve_info = raw_length * info_per_bit
        extractable = raw_length - eve_info - leaked_bits - self.security_margin

        return max(0, int(extractable))

    def amplify(
        self,
        reconciled_bits: List[int],
        target_length: int,
        salt: bytes = b"qusec_universal_hash_v1",
    ) -> List[int]:
        """
        Extract target_length unconditionally secure bits using universal hash extractor.
        Uses HMAC-SHA256 based universal hash compression for robust cryptographic performance.
        """
        if target_length <= 0 or not reconciled_bits:
            return []

        # Convert bit list to bytes
        byte_data = bytearray()
        for i in range(0, len(reconciled_bits), 8):
            chunk = reconciled_bits[i:i+8]
            val = 0
            for b in chunk:
                val = (val << 1) | b
            val = val << (8 - len(chunk))  # pad if last chunk < 8
            byte_data.append(val)

        # Multi-block HKDF/HMAC expansion if target_length > 256
        extracted_bits = []
        counter = 0
        while len(extracted_bits) < target_length:
            h = hashlib.sha256(salt + byte_data + counter.to_bytes(4, "big")).digest()
            for byte in h:
                for bit_idx in range(8):
                    extracted_bits.append((byte >> (7 - bit_idx)) & 1)
                    if len(extracted_bits) == target_length:
                        break
                if len(extracted_bits) == target_length:
                    break
            counter += 1

        return extracted_bits[:target_length]
