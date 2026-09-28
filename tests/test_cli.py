import subprocess
import json

def test_qusec_json_run():
    result = subprocess.run(
        ["qusec", "run", "--json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    
    data = json.loads(result.stdout)
    assert "session_id" in data
    assert "decision" in data
    assert data["decision"] == "VERIFIED"
