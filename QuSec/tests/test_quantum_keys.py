"""
Unit Tests for Quantum Asymmetric Key Generation, Public Key Encryption,
and Quantum Digital Signature (QDS) Verification in QuSec.
"""

import pytest
from qusec.crypto.quantum_keys import (
    QuantumKeyPair,
    QuantumPublicKey,
    QuantumPrivateKey,
    encrypt_with_quantum_public_key,
    decrypt_with_quantum_private_key,
    sign_with_quantum_private_key,
    verify_with_quantum_public_key,
)
from qusec.session.manager import SessionManager
from qusec.node import QuSecNode


def test_quantum_keypair_generation():
    """Verify that Sender and Receiver generate distinct Quantum Key Pairs."""
    sender_kp = QuantumKeyPair.generate(role="sender")
    receiver_kp = QuantumKeyPair.generate(role="receiver")

    assert sender_kp.private_key is not None
    assert sender_kp.public_key is not None
    assert receiver_kp.private_key is not None
    assert receiver_kp.public_key is not None

    # Check fingerprints
    assert sender_kp.public_key.fingerprint.startswith("Q-PK-SENDER-")
    assert sender_kp.private_key.fingerprint.startswith("Q-SK-SENDER-")
    assert receiver_kp.public_key.fingerprint.startswith("Q-PK-RECV-")
    assert receiver_kp.private_key.fingerprint.startswith("Q-SK-RECV-")
    assert sender_kp.public_key.fingerprint != receiver_kp.public_key.fingerprint


def test_quantum_public_key_encryption_and_private_key_decryption():
    """
    Verify requirement:
    Sender encrypts message using receiver's quantum public key.
    Receiver decrypts message using receiver's quantum private key.
    """
    receiver_kp = QuantumKeyPair.generate(role="receiver")
    original_message = "Confidential Quantum Teleportation State Coordinates 2026!"

    # Sender encrypts with Receiver's Quantum Public Key
    enc_payload = encrypt_with_quantum_public_key(original_message, receiver_kp.public_key)
    assert "ciphertext_hex" in enc_payload
    assert "enc_key_hex" in enc_payload
    assert "nonce_hex" in enc_payload

    # Receiver decrypts with Receiver's Quantum Private Key
    decrypted_text = decrypt_with_quantum_private_key(enc_payload, receiver_kp.private_key)
    assert decrypted_text == original_message


def test_quantum_digital_signature_signing_and_verification():
    """
    Verify requirement:
    Sender encrypts/signs quantum digital signature using its own quantum private key.
    Receiver verifies/decrypts signature using sender's quantum public key.
    """
    sender_kp = QuantumKeyPair.generate(role="sender")
    message = "Nuclear Authorization Token #429"

    # Sender signs with Sender's Quantum Private Key
    sig_payload = sign_with_quantum_private_key(message, sender_kp.private_key)
    assert "signature_hex" in sig_payload
    assert "signature_bits" in sig_payload
    assert sig_payload["sender_sk_fingerprint"] == sender_kp.private_key.fingerprint

    # Receiver verifies with Sender's Quantum Public Key
    valid, reason = verify_with_quantum_public_key(message, sig_payload, sender_kp.public_key)
    assert valid is True
    assert "Verified" in reason

    # Verification must fail if message is tampered
    tampered_message = "Nuclear Authorization Token #430 (TAMPERED)"
    invalid, err_reason = verify_with_quantum_public_key(tampered_message, sig_payload, sender_kp.public_key)
    assert invalid is False


def test_wrong_key_decryption_fails():
    """Verify that an unauthorized node cannot decrypt with a different private key."""
    bob_kp = QuantumKeyPair.generate(role="receiver")
    eve_kp = QuantumKeyPair.generate(role="receiver")

    message = "Secret payload for Bob only"
    enc_payload = encrypt_with_quantum_public_key(message, bob_kp.public_key)

    # Eve attempts to decrypt with her own private key -> must fail
    with pytest.raises(Exception):
        decrypt_with_quantum_private_key(enc_payload, eve_kp.private_key)


def test_session_manager_quantum_key_exchange():
    """Verify handshake exchange of Quantum Public Keys between Alice and Bob."""
    alice_mgr = SessionManager(role="sender")
    bob_mgr = SessionManager(role="receiver")

    # 1. Alice initiates handshake with her Quantum Public Key
    init_pkt = alice_mgr.initiate_handshake()
    assert "quantum_public_key" in init_pkt
    alice_pk_fingerprint = init_pkt["quantum_public_key"]["fingerprint"]

    # 2. Bob processes Alice's packet, records Alice's public key, responds with Bob's public key
    ack_pkt = bob_mgr.process_handshake_init(init_pkt)
    assert ack_pkt is not None
    assert "quantum_public_key" in ack_pkt
    assert bob_mgr.peer_public_key.fingerprint == alice_pk_fingerprint

    # 3. Alice completes handshake, records Bob's public key
    assert alice_mgr.complete_handshake(ack_pkt) is True
    assert alice_mgr.peer_public_key.fingerprint == bob_mgr.keypair.public_key.fingerprint


def test_node_send_message_quantum_keys():
    """Verify QuSecNode send_message populates public key encryption and private key signature."""
    node = QuSecNode(role="sender", force_simulation=True, gateway_port=18991)
    node.initialize()

    res = node.send_message("receiver", "Testing Quantum Asymmetric Keys", mode="teleportation")
    assert res["success"] is True
    assert "recipient_public_key" in res
    assert "sender_private_key" in res
    assert res["mode"] == "teleportation"

    node.stop()
