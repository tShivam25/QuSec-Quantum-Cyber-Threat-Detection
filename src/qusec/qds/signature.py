import hashlib
import os

def generate_key_material(length=20):
    """Generate random bits for key material."""
    return [int(b) for b in bin(int.from_bytes(os.urandom(length), 'big'))[2:].zfill(length*8)[:length]]

def generate_signature(message: str) -> list[int]:
    """
    SIMULATION SIGNATURE
    Generates a 16-bit signature by hashing the message with SHA-256 and taking 4 hex characters.
    """
    h = hashlib.sha256(message.encode('utf-8')).hexdigest()
    truncated_hex = h[:4]
    bit_str = bin(int(truncated_hex, 16))[2:].zfill(16)
    return [int(b) for b in bit_str]

def message_to_bits(message: str) -> list[int]:
    bits = []
    for char in message:
        bits.extend([int(b) for b in format(ord(char), '08b')])
    return bits

def construct_payload(message: str):
    msg_bits = message_to_bits(message)
    sig_bits = generate_signature(message)
    key_bits = generate_key_material(20) # 20 bits
    
    payload = msg_bits + sig_bits + key_bits
    
    metadata = {
        "message_start": 0,
        "message_end": len(msg_bits),
        "signature_start": len(msg_bits),
        "signature_end": len(msg_bits) + len(sig_bits),
        "key_start": len(msg_bits) + len(sig_bits),
        "key_end": len(payload)
    }
    return payload, metadata


class QuantumDigitalSignature:
    """
    Quantum Digital Signature protocol wrapper.
    Handles signature generation, verification, and payload assembly.
    """
    def __init__(self, key_length: int = 20):
        self.key_length = key_length

    def sign(self, message: str) -> list[int]:
        return generate_signature(message)

    def prepare_payload(self, message: str):
        return construct_payload(message)

    def verify(self, message: str, signature_bits: list[int]) -> bool:
        expected = generate_signature(message)
        return expected == signature_bits

