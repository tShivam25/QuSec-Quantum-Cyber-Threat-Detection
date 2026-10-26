import subprocess
import json
import sys
from qusec.detection.qber import hoeffding_margin, qber_from_correlator
from qusec.detection.threshold import ThresholdEngine

def test_qusec_json_run():
    result = subprocess.run(
        [sys.executable, "-m", "qusec.cli", "run", "--json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    
    data = json.loads(result.stdout)
    assert "session_id" in data
    assert "decision" in data
    assert data["decision"] == "VERIFIED"

def test_hoeffding_and_correlators():
    """Verify mathematical formulas for Hoeffding margin (Eq. 15) and correlator QBER (Eq. 13)."""
    # For n=10^4, delta=10^-3, epsilon approx 1.95% (paper Section VII)
    eps = hoeffding_margin(10000, 0.001)
    assert abs(eps - 0.0195) < 0.001

    # Ideal Bell pair correlator <ZZ> = 1 -> Q_Z = 0
    assert qber_from_correlator(1.0) == 0.0
    # Completely uncorrelated <ZZ> = 0 -> Q_Z = 0.5 (50%)
    assert qber_from_correlator(0.0) == 0.5

def test_two_threshold_transferability():
    """Verify Eq. 18 two-threshold verification and transferability guarantee."""
    engine = ThresholdEngine(sa=0.05, sv=0.15)
    
    # Honest signer with mismatch 0.01 -> VALID
    res_honest = engine.evaluate_signature(0.01)
    assert res_honest["verdict"] == "VALID"
    assert res_honest["is_valid"] is True
    assert res_honest["is_transferable"] is True
    
    # Borderline transferable: sa < m <= sv -> TRANSFERABLE
    res_trans = engine.evaluate_signature(0.10)
    assert res_trans["verdict"] == "TRANSFERABLE"
    assert res_trans["is_valid"] is False
    assert res_trans["is_transferable"] is True
    
    # Forgery: m > sv -> FORGED
    res_forged = engine.evaluate_signature(0.35)
    assert res_forged["verdict"] == "FORGED"
    assert res_forged["is_valid"] is False
    assert res_forged["is_transferable"] is False

def test_qusec_interactive_chat(monkeypatch):
    """Verify qusec chat command starts, responds to commands, and exits cleanly on /quit."""
    from qusec.node import QuSecNode
    node = QuSecNode(role="sender", force_simulation=True, gateway_port=8992)
    inputs = iter(["/status", "/quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    node.run_interactive_chat()
    assert node.is_running is False
