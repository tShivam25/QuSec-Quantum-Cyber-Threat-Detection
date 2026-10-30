"""
Unit and Integration Tests for QuSec Adaptive QBER Threshold Engine and 3 Quantum Backends.
Validates:
1. Mathematical auto-adjusting QBER threshold based on finite-key Hoeffding bounds and Raman scattering traffic.
2. 3 Execution backends: AerSimulator, Noisy AerSimulator, and Quantum Hardware.
3. Decision logic and mathematical proof dictionary integrity.
"""

import time
import pytest
from qusec.detection.threshold import DynamicThresholdEngine
from qusec.quantum.backend import (
    normalize_backend_type,
    get_backend_label,
    get_backend,
    execute_circuit,
)
from qiskit import QuantumCircuit


def test_dynamic_threshold_mathematical_bounds():
    """Verify that dynamic threshold auto-adjusts within theoretical quantum security bounds."""
    engine = DynamicThresholdEngine(
        baseline_q0=0.015,
        alpha_traffic=0.012,
        beta_stat=0.28,
        confidence_delta=0.001,
        max_qber_ceiling=0.110,
        min_qber_floor=0.035,
    )

    # 1. Finite-sample scaling: Short message (n=16 qubits) vs Long message (n=512 qubits)
    q_short, proof_short = engine.compute_threshold(sample_size_n=16, traffic_rate_phi=0.0)
    q_long, proof_long = engine.compute_threshold(sample_size_n=512, traffic_rate_phi=0.0)

    # Shorter message has higher statistical uncertainty -> higher Hoeffding margin
    assert proof_short["delta_stat"] > proof_long["delta_stat"]
    assert q_short > q_long

    # 2. Traffic rate scaling: Quiescent channel (Phi=0) vs Heavy traffic (Phi=15 msgs/sec)
    q_low_traffic, proof_low = engine.compute_threshold(sample_size_n=128, traffic_rate_phi=0.0)
    q_high_traffic, proof_high = engine.compute_threshold(sample_size_n=128, traffic_rate_phi=15.0)

    assert proof_high["delta_traffic"] > proof_low["delta_traffic"]
    assert q_high_traffic > q_low_traffic

    # 3. Maximum ceiling test (Scarani et al. 2009 limit: 11.0%)
    # Even under extreme traffic (Phi=1000) and tiny sample (n=1), Qth must NEVER exceed 11%
    q_extreme, proof_extreme = engine.compute_threshold(sample_size_n=1, traffic_rate_phi=1000.0)
    assert q_extreme <= 0.110
    assert abs(q_extreme - 0.110) < 1e-6

    # 4. Minimum floor test
    # Even with huge sample (n=100,000) and zero traffic, Qth must stay >= floor (3.5%)
    q_floor, _ = engine.compute_threshold(sample_size_n=100000, traffic_rate_phi=0.0)
    assert q_floor >= 0.035


def test_traffic_tracker_sliding_window():
    """Verify sliding window traffic tracking (messages per second)."""
    engine = DynamicThresholdEngine(window_seconds=2.0)

    # Initially zero
    assert engine.get_traffic_rate() == 0.0

    # Record 5 message transmissions
    for _ in range(5):
        engine.record_transmission()

    rate = engine.get_traffic_rate()
    assert rate > 0.0

    # Auto-adjusting threshold without explicit traffic parameter uses the live sliding window
    q_live, proof_live = engine.compute_threshold(sample_size_n=32)
    assert proof_live["traffic_rate_phi"] == rate
    assert proof_live["confidence_level"] == 0.999


def test_mathematical_security_decision():
    """Verify acceptance of clean quantum transmission and rejection of tampering."""
    engine = DynamicThresholdEngine(baseline_q0=0.015)

    # Case A: Clean transmission (QBER = 1.8%, well below dynamic threshold ~ 5.5%)
    eval_clean = engine.evaluate_channel_security(measured_qber=0.018, sample_size_n=64)
    assert eval_clean["status"] == "SECURE"
    assert eval_clean["attack_detected"] is False
    assert eval_clean["qber"] == 0.018
    assert eval_clean["threshold"] >= 0.035
    assert "proof" in eval_clean
    assert "min(0.110" in eval_clean["proof"]["formula"]

    # Case B: Severe eavesdropping / intercept-resend attack (QBER = 25.0%, above ceiling 11.0%)
    eval_attack = engine.evaluate_channel_security(measured_qber=0.250, sample_size_n=64)
    assert eval_attack["status"] == "THREAT DETECTED"
    assert eval_attack["attack_detected"] is True
    assert eval_attack["qber"] == 0.250
    assert eval_attack["qber"] > eval_attack["threshold"]


def test_three_execution_backends():
    """Verify normalization, labeling, and initialization of all 3 quantum execution backends."""
    # 1. Normalization
    assert normalize_backend_type("1") == "simulator"
    assert normalize_backend_type("aer") == "simulator"
    assert normalize_backend_type("2") == "noisy"
    assert normalize_backend_type("noisy_aer") == "noisy"
    assert normalize_backend_type("3") == "hardware"
    assert normalize_backend_type("quantum_hardware") == "hardware"
    assert normalize_backend_type("unknown") == "simulator"

    # 2. Labels
    label_sim = get_backend_label("1")
    assert "Aersim" in label_sim or "AerSim" in label_sim or "AerSimulator" in label_sim
    assert "Ideal" in label_sim

    label_noisy = get_backend_label("2")
    assert "Noisy AerSim" in label_noisy or "Noisy AerSimulator" in label_noisy

    label_hw = get_backend_label("3")
    assert "Quantum Hardware" in label_hw

    # 3. Execution on Backend 1 (AerSimulator)
    qc = QuantumCircuit(1, 1)
    qc.x(0)
    qc.measure(0, 0)
    counts_sim = execute_circuit(qc, backend_type="simulator", shots=10)
    assert "1" in counts_sim
    assert counts_sim["1"] == 10

    # 4. Execution on Backend 2 (Noisy AerSimulator)
    counts_noisy = execute_circuit(qc, backend_type="noisy", shots=50)
    assert "1" in counts_noisy
    # In depolarizing noise channel, most counts are "1", with occasional bit flip
    assert counts_noisy["1"] >= 40

    # 5. Backend 3 (Hardware fallback when no cloud credentials provided)
    backend_hw = get_backend("hardware")
    assert backend_hw is not None
