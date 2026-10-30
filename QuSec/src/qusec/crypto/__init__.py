"""
QuSec Cryptographic Subsystem: One-Time-Pad and Wegman-Carter Authentication.
"""

from qusec.crypto.otp import OneTimePad, string_to_bits, bits_to_string
from qusec.crypto.auth import WegmanCarterMAC
from qusec.crypto.quantum_keys import (
    QuantumPublicKey,
    QuantumPrivateKey,
    QuantumKeyPair,
    encrypt_with_quantum_public_key,
    decrypt_with_quantum_private_key,
    sign_with_quantum_private_key,
    verify_with_quantum_public_key,
)

__all__ = [
    "OneTimePad",
    "string_to_bits",
    "bits_to_string",
    "WegmanCarterMAC",
    "QuantumPublicKey",
    "QuantumPrivateKey",
    "QuantumKeyPair",
    "encrypt_with_quantum_public_key",
    "decrypt_with_quantum_private_key",
    "sign_with_quantum_private_key",
    "verify_with_quantum_public_key",
]

