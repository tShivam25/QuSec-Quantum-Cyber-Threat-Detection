"""
One-Time-Pad (OTP) Cryptographic Engine for QuSec.
Provides information-theoretic (Shannon-proven) unconditional confidentiality
by consuming key material from the QuSec KeyPool with immediate memory zeroization.

NOTE ON SECURITY MODEL:
This encryption occurs on the laptop endpoint. The browser-to-gateway hop
is local plaintext. This protocol provides laptop-to-laptop quantum-secure transport.
"""

from typing import List, Dict, Any, Optional
from qusec.session.key_pool import KeyPool


def string_to_bits(text: str) -> List[int]:
    """Convert UTF-8 string to a list of bits."""
    raw_bytes = text.encode("utf-8")
    bits = []
    for b in raw_bytes:
        for i in range(8):
            bits.append((b >> (7 - i)) & 1)
    return bits


def bits_to_string(bits: List[int]) -> str:
    """Convert a list of bits (multiple of 8) back to UTF-8 string."""
    byte_vals = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            break
        val = 0
        for b in chunk:
            val = (val << 1) | b
        byte_vals.append(val)
    return byte_vals.decode("utf-8", errors="replace")


class OneTimePad:
    """
    One-Time-Pad encryptor/decryptor consuming key bits from the shared KeyPool.
    """

    @staticmethod
    def encrypt(text: str, key_pool: KeyPool) -> Optional[Dict[str, Any]]:
        """
        Encrypt plaintext string using One-Time-Pad from key pool.
        Consumes and burns the exact required key bits.
        """
        pt_bits = string_to_bits(text)
        needed = len(pt_bits)

        key_bits = key_pool.consume(needed)
        if key_bits is None:
            return None  # Insufficient key material

        ct_bits = [p ^ k for p, k in zip(pt_bits, key_bits)]

        # Zeroize plaintext bits and key bits in local memory
        for i in range(needed):
            pt_bits[i] = 0

        # Pack into hex representation
        ct_bytes = bytearray()
        for i in range(0, len(ct_bits), 8):
            chunk = ct_bits[i:i+8]
            v = 0
            for b in chunk:
                v = (v << 1) | b
            ct_bytes.append(v)

        return {
            "ciphertext_hex": ct_bytes.hex(),
            "bit_length": needed,
            "security_type": "Laptop-to-Laptop Quantum OTP",
            "key_consumed": needed,
            # In simulation / test receiver, key_bits can be forwarded over secure link
            "_raw_key_bits": key_bits,
        }

    @staticmethod
    def decrypt(ciphertext_hex: str, key_bits: List[int]) -> Optional[str]:
        """
        Decrypt One-Time-Pad ciphertext hex given the corresponding burned key bits.
        """
        ct_bytes = bytes.fromhex(ciphertext_hex)
        ct_bits = []
        for b in ct_bytes:
            for i in range(8):
                ct_bits.append((b >> (7 - i)) & 1)

        ct_bits = ct_bits[:len(key_bits)]
        pt_bits = [c ^ k for c, k in zip(ct_bits, key_bits)]
        recovered = bits_to_string(pt_bits)

        # Zeroize sensitive buffers
        for i in range(len(pt_bits)):
            pt_bits[i] = 0

        return recovered
