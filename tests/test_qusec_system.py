"""
Comprehensive Test Suite for QuSec Quantum Transport & Real-World System.
Tests hardware drivers, entanglement engine, CHSH inequality, SARG04 sifting,
Cascade error correction, Privacy Amplification, Quantum Teleportation,
OTP encryption, KeyPool, SessionManager, and CLI commands.
"""

import subprocess
import sys
import json
import time
import pytest

from qusec.hardware.optical import QuantumChannel, EthernetDetector
from qusec.hardware.classical import ClassicalChannel
from qusec.hardware.rng import RandomSource
from qusec.hardware.doctor import run_doctor
from qusec.quantum.entanglement import EntanglementEngine
from qusec.quantum.teleport import QuantumTeleportationEngine
from qusec.protocol.sarg04 import SARG04ProtocolEngine
from qusec.protocol.cascade import CascadeReconciler
from qusec.protocol.privacy import PrivacyAmplifier
from qusec.session.key_pool import KeyPool
from qusec.session.manager import SessionManager, SessionState
from qusec.crypto.otp import OneTimePad, string_to_bits, bits_to_string
from qusec.crypto.auth import WegmanCarterMAC
from qusec.node import QuSecNode


def test_doctor_self_test():
    """Verify that qusec doctor executes cleanly and returns structured diagnostic data."""
    report = run_doctor()
    assert report["python_ok"] is True
    assert "optical_socket_ok" in report
    assert "classical_socket_ok" in report
    assert isinstance(report["esp32_devices"], list)
    assert isinstance(report["ethernet_interfaces"], list)


def test_ethernet_auto_detection():
    """Verify that Ethernet interfaces are correctly parsed on system."""
    ifaces = EthernetDetector.get_interfaces()
    assert len(ifaces) > 0
    # On macOS, at least loopback or physical en0 exists
    names = [i["name"] for i in ifaces]
    assert any(n.startswith("en") or n.startswith("lo") for n in names)


def test_random_source_entropy():
    """Verify RandomSource produces random bits, bytes, and choices."""
    rng = RandomSource(force_simulation=True)
    raw_bytes = rng.get_random_bytes(32)
    assert len(raw_bytes) == 32
    assert isinstance(raw_bytes, bytes)

    bits = rng.get_random_bits(128)
    assert len(bits) == 128
    assert all(b in (0, 1) for b in bits)

    chosen = rng.choice(["Z", "X"])
    assert chosen in ["Z", "X"]


def test_entanglement_chsh_violation():
    """Verify that ideal Bell states violate the CHSH classical bound (S > 2.0)."""
    engine = EntanglementEngine(backend_type="simulator")
    res = engine.measure_chsh_correlators(num_shots_per_setting=300)

    # Quantum mechanics predicts S approx 2.828, bound is 2.0
    assert res["CHSH_S"] > 2.0, f"Expected CHSH S > 2.0, got {res['CHSH_S']}"
    assert res["violation"] is True
    assert res["trusted"] is True
    assert res["fidelity"] >= 0.85


def test_entanglement_chsh_under_attack():
    """Verify that an intercept-resend attack degrades CHSH correlation below or near classical bound."""
    engine = EntanglementEngine(backend_type="simulator")
    res_attack = engine.measure_chsh_correlators(num_shots_per_setting=300, attack_type="intercept_resend")

    # Under complete intercept-resend, quantum entanglement is destroyed
    assert res_attack["CHSH_S"] < 2.2


def test_quantum_teleportation_fidelity():
    """Verify quantum state teleportation succeeds when sender and Bob bases match."""
    teleporter = QuantumTeleportationEngine(backend_type="simulator")

    # Test bit 0 and bit 1 teleportation in Z basis
    res_0 = teleporter.teleport_single_qubit(input_bit=0, sender_basis="Z", bob_basis="Z")
    assert res_0["bob_bit"] == 0
    assert res_0["success"] is True

    res_1 = teleporter.teleport_single_qubit(input_bit=1, sender_basis="Z", bob_basis="Z")
    assert res_1["bob_bit"] == 1
    assert res_1["success"] is True


def test_sarg04_sifting_and_decoys():
    """Verify SARG04 state preparation, decoy state tags, and non-orthogonal sifting."""
    sarg = SARG04ProtocolEngine()
    prep = sarg.prepare_states(num_qubits=200)

    assert len(prep["bits"]) == 200
    assert len(prep["candidates"]) == 200
    assert set(prep["decoys"]).issubset({"mu", "nu", "vac"})

    meas = sarg.measure_states(200, prep["bits"], prep["bases"], channel_error_rate=0.01)
    sifted = sarg.sift_keys(prep, meas)

    assert sifted["conclusive_count"] > 0
    assert sifted["qber"] < 0.08  # Baseline channel error


def test_cascade_error_correction():
    """Verify Cascade multi-pass parity search eliminates bit flips between Alice and Bob."""
    alice_bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1] * 5  # 100 bits
    bob_bits = list(alice_bits)

    # Inject 3 bit flips (3% error rate)
    bob_bits[12] = 1 - bob_bits[12]
    bob_bits[45] = 1 - bob_bits[45]
    bob_bits[78] = 1 - bob_bits[78]

    reconciler = CascadeReconciler(target_qber=0.03, num_passes=4)
    res = reconciler.reconcile(alice_bits, bob_bits, seed=123)

    assert res["residual_errors"] == 0
    assert res["reconciled_bob"] == alice_bits
    assert res["corrected_errors"] >= 3
    assert res["leaked_bits"] > 0


def test_privacy_amplification():
    """Verify Privacy Amplification compresses reconciled key to extract pure secret bits."""
    amplifier = PrivacyAmplifier(security_margin=16)
    sec_len = amplifier.calculate_secure_length(raw_length=500, qber=0.02, leaked_bits=40)
    assert sec_len > 0

    reconciled_bits = [1, 0, 1, 1, 0] * 100
    secret_key = amplifier.amplify(reconciled_bits, target_length=sec_len)
    assert len(secret_key) == sec_len
    assert all(b in (0, 1) for b in secret_key)


def test_key_pool_lifecycle_and_zeroization():
    """Verify KeyPool key addition, consumption, and immediate zeroization burn."""
    pool = KeyPool(rekey_threshold=50, target_pool_size=200)
    assert pool.available_bits == 0
    assert pool.needs_rekey() is True

    pool.add_keys([1, 0, 1, 1, 0, 1, 0, 0] * 10)  # 80 bits
    assert pool.available_bits == 80
    assert pool.needs_rekey() is False

    consumed = pool.consume(20)
    assert len(consumed) == 20
    assert pool.available_bits == 60
    assert pool.stats["total_burned_bits"] == 20

    pool.burn_all()
    assert pool.available_bits == 0


def test_one_time_pad_encryption():
    """Verify One-Time-Pad encrypts and decrypts with exact round-trip fidelity."""
    pool = KeyPool(rekey_threshold=100)
    # Seed pool with random bits
    rng = RandomSource(force_simulation=True)
    pool.add_keys(rng.get_random_bits(1024))

    secret_message = "QuSec Quantum Secret 2026!"
    otp_res = OneTimePad.encrypt(secret_message, pool)
    assert otp_res is not None
    assert "ciphertext_hex" in otp_res
    assert otp_res["bit_length"] == len(secret_message.encode("utf-8")) * 8

    # Decrypt
    decrypted = OneTimePad.decrypt(otp_res["ciphertext_hex"], otp_res["_raw_key_bits"])
    assert decrypted == secret_message


def test_wegman_carter_mac():
    """Verify Wegman-Carter MAC authentication tag generation and tamper detection."""
    msg = b"sarg04_candidate_pair_announcement_frame"
    key = b"super_secret_one_time_auth_key_128"

    mac = WegmanCarterMAC.authenticate_message(msg, key)
    assert WegmanCarterMAC.verify_mac(msg, key, mac) is True

    # Tampered message must fail MAC verification
    tampered_msg = b"sarg04_candidate_pair_announcement_fraMe"
    assert WegmanCarterMAC.verify_mac(tampered_msg, key, mac) is False


def test_session_manager_handshake_and_abort():
    """Verify SessionManager handshake negotiation and QBER abort trigger."""
    alice_mgr = SessionManager(role="alice", qber_threshold=0.06)
    bob_mgr = SessionManager(role="bob", qber_threshold=0.06)

    # Handshake
    init_pkt = alice_mgr.initiate_handshake()
    ack_pkt = bob_mgr.process_handshake_init(init_pkt)
    assert ack_pkt is not None
    assert bob_mgr.state == SessionState.ESTABLISHED

    assert alice_mgr.complete_handshake(ack_pkt) is True
    assert alice_mgr.state == SessionState.ESTABLISHED

    # Simulate QBER threat > 6%
    alice_mgr.update_channel_metrics(qber=0.085, fidelity=0.80, chsh=1.85)
    assert alice_mgr.state == SessionState.ABORTED
    assert alice_mgr.channel_trusted is False


def test_node_full_pipeline_run():
    """Run full QuSec node pipeline in simulation mode for 1 second."""
    node = QuSecNode(
        role="sender",
        optical_port=19888,
        classical_port=19889,
        gateway_port=18765,
        force_simulation=True,
    )
    assert node.initialize() is True
    assert node.key_pool.available_bits > 1000

    # Test send message via quantum teleportation
    teleport_res = node.send_message(recipient="receiver", message="Hi Receiver", mode="teleportation")
    assert teleport_res["success"] is True
    assert teleport_res["mode"] == "teleportation"

    # Test send message via OTP
    otp_res = node.send_message(recipient="receiver", message="Secret", mode="otp")
    assert otp_res["success"] is True
    assert otp_res["mode"] == "otp"

    node.stop()


def test_bidirectional_chat_between_sender_and_receiver():
    """Verify full-duplex communication: Sender sends to Receiver, Receiver replies to Sender."""
    sender_node = QuSecNode(
        role="sender",
        peer_host="127.0.0.1",
        optical_port=19910,
        classical_port=19911,
        peer_optical_port=19912,
        peer_classical_port=19913,
        gateway_port=18780,
        force_simulation=True,
    )
    receiver_node = QuSecNode(
        role="receiver",
        peer_host="127.0.0.1",
        optical_port=19912,
        classical_port=19913,
        peer_optical_port=19910,
        peer_classical_port=19911,
        gateway_port=18781,
        force_simulation=True,
    )

    assert sender_node.initialize() is True
    assert receiver_node.initialize() is True
    time.sleep(0.3)

    # 1. Sender transmits to Receiver
    send_res = sender_node.send_message(recipient="receiver", message="Hello Receiver!", mode="teleportation")
    assert send_res["success"] is True

    # Allow listener thread to process
    time.sleep(0.4)
    assert len(receiver_node.received_messages) >= 1
    assert receiver_node.received_messages[-1]["text"] == "Hello Receiver!"
    assert receiver_node.received_messages[-1]["from"] == "Sender"

    # 2. Receiver replies back to Sender
    reply_res = receiver_node.send_message(recipient="sender", message="Hello Sender, received!", mode="teleportation")
    assert reply_res["success"] is True

    time.sleep(0.4)
    assert len(sender_node.received_messages) >= 1
    assert sender_node.received_messages[-1]["text"] == "Hello Sender, received!"
    assert sender_node.received_messages[-1]["from"] == "Receiver"

    sender_node.stop()
    receiver_node.stop()


def test_cli_subcommands():
    """Verify CLI subcommands via subprocess: doctor, keys, send, run."""
    # 1. qusec doctor
    res_doc = subprocess.run([sys.executable, "-m", "qusec.cli", "doctor"], capture_output=True, text=True)
    assert res_doc.returncode == 0
    assert "QuSec System Diagnostics Doctor" in res_doc.stdout

    # 2. qusec keys
    res_keys = subprocess.run([sys.executable, "-m", "qusec.cli", "keys"], capture_output=True, text=True)
    assert res_keys.returncode == 0
    assert "QuSec Cryptographic Key Pool Status" in res_keys.stdout

    # 3. qusec send
    res_send = subprocess.run([sys.executable, "-m", "qusec.cli", "send", "--to", "bob", "Test Message"], capture_output=True, text=True)
    assert res_send.returncode == 0
    assert "Message delivered via TELEPORTATION!" in res_send.stdout or "Message sent" in res_send.stdout

    # 4. qusec version
    res_ver = subprocess.run([sys.executable, "-m", "qusec.cli", "version"], capture_output=True, text=True)
    assert res_ver.returncode == 0
    assert "QuSec v" in res_ver.stdout

    # 5. qusec run --json (legacy verification)
    res_run = subprocess.run([sys.executable, "-m", "qusec.cli", "run", "--json"], capture_output=True, text=True)
    assert res_run.returncode == 0
    data = json.loads(res_run.stdout)
    assert data["decision"] == "VERIFIED"
