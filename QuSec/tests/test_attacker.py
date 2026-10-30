"""
Tests for QuSec Attacker Engine and Bidirectional Node Security Reporting.
Validates:
1. Attacker engine tampering capabilities, dynamic QBER thresholding, and entropy.
2. Bidirectional transmission: Node A -> Node B AND Node B -> Node A both generate
   complete QuSec Quantum Security Reports on their respective receiver nodes.
"""

import time
import json
import pytest
from qusec.attacker import QuSecAttacker, AttackerESP32Device
from qusec.node import QuSecNode


def test_attacker_tampering_and_interference():
    """Verify QuSecAttacker bit manipulation, Pauli noise, and dynamic calculations."""
    attacker = QuSecAttacker(
        target_host="127.0.0.1",
        target_port=9876,
        esp_port=None,
        qber_baseline=0.045,
    )

    # 1. Hardware device fallback to simulated hardware TRNG
    assert attacker.esp.connected is False
    rand_bytes = attacker.esp.get_hardware_entropy(16)
    assert len(rand_bytes) == 16
    assert isinstance(rand_bytes, bytes)

    # 2. Dynamic QBER calculation under different traffic rates
    q_low = attacker.compute_dynamic_qber(sample_size=1024, traffic_rate=0.0)
    q_high = attacker.compute_dynamic_qber(sample_size=1024, traffic_rate=8.0)
    assert q_high > q_low
    assert q_low <= 0.110
    assert q_high <= 0.110

    # 3. Qubit frame tampering
    raw_frame = json.dumps({
        "type": "QUBIT_BURST",
        "sender": "alice",
        "c0": 0,
        "c1": 1,
        "payload": [1, 0, 1, 1],
    }).encode("utf-8")

    tampered_bytes = attacker.tamper_qubit_frame(raw_frame, error_rate=1.0)
    tampered_json = json.loads(tampered_bytes.decode("utf-8"))
    assert "qubit_tampered" in tampered_json
    assert tampered_json["qubit_tampered"] is True

    # 4. Classical packet tampering
    raw_classical = json.dumps({
        "type": "OTP_MESSAGE",
        "ciphertext": "01010101",
        "mac": "abcdef123456",
    }).encode("utf-8")

    tampered_classical = attacker.tamper_classical_packet(raw_classical, error_rate=1.0)
    tampered_cl_json = json.loads(tampered_classical.decode("utf-8"))
    assert tampered_cl_json["mac"] != "abcdef123456"

    # 5. Execute single burst attack
    result = attacker.attack_once(attack_type="tamper", rate=0.25)
    assert result["success"] is True
    assert result["attack_type"] == "tamper"
    assert attacker.stats["tampered_packets"] >= 1


def test_bidirectional_qusec_reporting():
    """
    Verify that in dual mode, transmission in BOTH directions:
    1. Laptop A -> Laptop B produces a complete QuSec report on Node B.
    2. Laptop B -> Laptop A produces a complete QuSec report on Node A.
    """
    node_a = QuSecNode(
        role="sender",
        peer_host="127.0.0.1",
        optical_port=19940,
        classical_port=19941,
        peer_optical_port=19942,
        peer_classical_port=19943,
        gateway_port=18795,
        force_simulation=True,
    )

    node_b = QuSecNode(
        role="receiver",
        peer_host="127.0.0.1",
        optical_port=19942,
        classical_port=19943,
        peer_optical_port=19940,
        peer_classical_port=19941,
        gateway_port=18796,
        force_simulation=True,
    )

    try:
        assert node_a.initialize() is True
        assert node_b.initialize() is True
        time.sleep(0.4)

        # ---------------------------------------------------------------------
        # Direction 1: Node A sends to Node B
        # ---------------------------------------------------------------------
        send_res_a = node_a.send_message(
            recipient="node_b",
            message="Hello from Node A!",
            mode="teleportation"
        )
        assert send_res_a["success"] is True

        # Wait for Node B to receive and process
        time.sleep(0.6)

        assert len(node_b.received_messages) >= 1
        msg_b = node_b.received_messages[-1]
        assert msg_b["sender"].lower() in ("sender", "node_a", "alice")
        assert msg_b["text"] == "Hello from Node A!"
        assert msg_b["qusec_report"] is not None
        assert "dynamic_threshold" in msg_b["qusec_report"]
        assert node_b.gateway_ctx.last_security_report is not None

        # ---------------------------------------------------------------------
        # Direction 2: Node B sends to Node A (The previously missing report)
        # ---------------------------------------------------------------------
        send_res_b = node_b.send_message(
            recipient="node_a",
            message="Hello back from Node B!",
            mode="teleportation"
        )
        assert send_res_b["success"] is True

        # Wait for Node A to receive and process
        time.sleep(0.6)

        assert len(node_a.received_messages) >= 1
        msg_a = node_a.received_messages[-1]
        assert msg_a["sender"].lower() in ("receiver", "node_b", "bob")
        assert msg_a["text"] == "Hello back from Node B!"
        assert msg_a["qusec_report"] is not None
        assert "dynamic_threshold" in msg_a["qusec_report"]
        assert node_a.gateway_ctx.last_security_report is not None
        assert node_a.gateway_ctx.last_security_report["recipient"].lower() in ("sender", "node_a")

    finally:
        node_a.stop()
        node_b.stop()
