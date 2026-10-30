"""
QuSec Adversary Framework & Cyber Threat Demonstrator (Eve)
============================================================
Simulates quantum and classical threat vectors against the QuSec Quantum Security system:
1. Quantum Channel Intercept-Resend & State Disturbance (Dynamic QBER Injection)
2. Classical Coordinate Tampering (Pauli Inversion Attack on c0, c1 via Hardware TRNG)
3. Impersonation & Forgery Attack (Wegman-Carter MAC Bypass Attempt)
4. Classical Replay Attack (Stale Frame Re-transmission)
5. Real-Time Man-in-the-Middle (MITM) Sniffer & In-Flight Packet Tamper Proxy
6. Denial-of-Service / Jamming Burst via ESP32 Hardware TRNG
7. Random In-Between Chat Auto-Attack Engine (Automated stealth attacks while users chat)

Terminal Interface:
- Sleek modern developer CLI: sleek dark typography, rounded containers, high density,
  command prompt, live telemetry, and slash command integration.
"""

import os
import sys
import time
import json
import uuid
import random
import socket
import logging
import threading
import argparse
from typing import Optional, Dict, Any, List, Tuple

# Attempt imports for serial and rich
try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    serial = None
    HAS_SERIAL = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    Console = None
    Table = None
    Panel = None
    Text = None
    box = None
    HAS_RICH = False

# Ensure QuSec package imports resolve if available
try:
    from qusec.crypto.otp import string_to_bits, bits_to_string
    from qusec.detection.qber import hoeffding_margin
    from qusec.detection.threshold import DynamicThresholdEngine
except ImportError:
    def string_to_bits(text: str) -> List[int]:
        raw_bytes = text.encode("utf-8")
        bits = []
        for b in raw_bytes:
            for i in range(8):
                bits.append((b >> (7 - i)) & 1)
        return bits

    def bits_to_string(bits: List[int]) -> str:
        byte_vals = bytearray()
        for i in range(0, len(bits), 8):
            chunk = bits[i:i + 8]
            if len(chunk) < 8:
                break
            val = 0
            for b in chunk:
                val = (val << 1) | b
            byte_vals.append(val)
        return byte_vals.decode("utf-8", errors="replace")

    def hoeffding_margin(n: int, delta: float = 0.001) -> float:
        import math
        if n <= 0:
            return 0.0
        return math.sqrt(math.log(2.0 / delta) / (2.0 * n))

    class DynamicThresholdEngine:
        def __init__(self, baseline_q0: float = 0.010, alpha_traffic: float = 0.012, **kwargs):
            self.baseline_q0 = baseline_q0
            self.alpha_traffic = alpha_traffic
            self.q_threshold = 0.06

        def get_traffic_rate(self) -> float:
            return 0.0

        def compute_dynamic_threshold(self, sample_size: int = 32, message_length: int = 0) -> Dict[str, Any]:
            return {
                "q_dyn": 0.0614,
                "q_floor": 0.035,
                "q_ceiling": 0.110,
                "traffic_rate_phi": 0.0,
                "delta_traffic": 0.0,
                "delta_stat": 0.0114,
                "sample_size_n": sample_size,
            }

logger = logging.getLogger("qusec.attacker")

DEFAULT_CLASSICAL_PORT = 9877
DEFAULT_OPTICAL_PORT = 9876
DEFAULT_BAUD_RATE = 115200

ESP32_KNOWN_VID_PID = {
    (0x10C4, 0xEA60): "Silicon Labs CP210x (ESP32)",
    (0x1A86, 0x7523): "QinHeng CH340 (ESP32)",
    (0x1A86, 0x55D4): "QinHeng CH343 / CH9102 (ESP32)",
    (0x303A, 0x1001): "Espressif USB JTAG/serial (ESP32-S3/C3)",
    (0x303A, 0x0002): "Espressif ESP32-S2 USB",
    (0x0403, 0x6001): "FTDI FT232R (ESP32 DevKit)",
}


class AttackerESP32Device:
    """Hardware controller for the Attacker's ESP32 microcontroller (Eve)."""

    def __init__(self, port: Optional[str] = None, baudrate: int = DEFAULT_BAUD_RATE, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[Any] = None
        self.is_connected = False
        self.firmware_version = "Unknown"
        self.role = "ATTACKER"
        self.description = "ESP32 Attacker Board"

    def auto_detect_and_connect(self, preferred_port: Optional[str] = None) -> bool:
        """Scan USB serial ports and connect to an ESP32 board."""
        if not HAS_SERIAL:
            logger.warning("pyserial is not installed. ESP32 hardware bridge disabled.")
            return False

        target_port = preferred_port or self.port
        if not target_port:
            try:
                ports = list(serial.tools.list_ports.comports())
                for p in ports:
                    vid_pid = (p.vid, p.pid)
                    desc_lower = (p.description or "").lower()
                    if vid_pid in ESP32_KNOWN_VID_PID or any(k in desc_lower for k in ["cp210", "ch340", "ch341", "esp32", "usb to uart", "ft232"]):
                        target_port = p.device
                        self.description = p.description or "ESP32 Board"
                        break
            except Exception as e:
                logger.debug("Port scanning error: %s", e)

        if not target_port:
            return False

        self.port = target_port
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            self._serial.dtr = False
            self._serial.rts = False
            time.sleep(0.15)
            self.is_connected = True

            resp = self.send_command("PING")
            if resp and isinstance(resp, dict):
                self.firmware_version = resp.get("fw", "2.5.0-ATTACKER")
            else:
                self.firmware_version = "2.5.0-ATTACKER"

            self.send_command("SET_ROLE ATTACKER")
            return True
        except Exception as e:
            logger.warning("Failed connecting to ESP32 on %s: %s", target_port, e)
            self.is_connected = False
            return False

    def disconnect(self):
        """Close serial interface."""
        if self._serial and getattr(self._serial, "is_open", False):
            try:
                self.set_alarm(False)
                self._serial.close()
            except Exception:
                pass
        self.is_connected = False

    def send_command(self, cmd: str) -> Optional[Any]:
        """Send command to ESP32 firmware and receive JSON response."""
        if not self.is_connected or not self._serial:
            return None
        try:
            self._serial.write((cmd.strip() + "\n").encode("utf-8"))
            self._serial.flush()
            line = self._serial.readline().decode("utf-8", errors="replace").strip()
            if not line:
                return None
            try:
                return json.loads(line)
            except Exception:
                return {"raw": line}
        except Exception as e:
            logger.debug("Serial command '%s' failed: %s", cmd, e)
            return None

    def get_trng_bytes(self, num_bytes: int = 32) -> bytes:
        """Fetch true hardware random bytes from ESP32 esp_random() generator."""
        if self.is_connected:
            resp = self.send_command(f"RNG {num_bytes}")
            if isinstance(resp, dict) and "hex" in resp:
                try:
                    return bytes.fromhex(resp["hex"])
                except Exception:
                    pass
        return os.urandom(num_bytes)

    @property
    def connected(self) -> bool:
        """Alias for is_connected."""
        return self.is_connected

    def get_hardware_entropy(self, num_bytes: int = 32) -> bytes:
        """Alias for get_trng_bytes."""
        return self.get_trng_bytes(num_bytes)

    def set_alarm(self, enable: bool = True, blink_ms: int = 100) -> bool:
        """Control Attacker ESP32 attack blast LED (GPIO 4)."""
        if not self.is_connected:
            return False
        cmd = f"ALARM {'1' if enable else '0'} {blink_ms}"
        resp = self.send_command(cmd)
        return bool(resp and isinstance(resp, dict) and resp.get("status") == "OK")

    def transmit_wifi_packet(self, packet_bytes: bytes) -> bool:
        """Transmit packet wirelessly via ESP32 Wi-Fi relay (TX command)."""
        if not self.is_connected:
            return False
        hex_data = packet_bytes.hex()
        resp = self.send_command(f"TX {hex_data}")
        return bool(resp and isinstance(resp, dict) and resp.get("status") == "OK")

    def trigger_jamming(self, count: int = 15, delay_ms: int = 10) -> bool:
        """Trigger hardware TRNG jamming burst on the ESP32."""
        if not self.is_connected:
            return False
        resp = self.send_command(f"JAM {count} {delay_ms}")
        return bool(resp and isinstance(resp, dict) and resp.get("status") == "OK")


class QuSecAttacker:
    """
    Primary Adversary Demonstration Engine (Eve).
    Implements cyber threat vectors against classical and quantum transport channels.
    Includes modern developer TUI styling and automated random in-between chat attacks.
    """

    def __init__(
        self,
        target_host: str = "127.0.0.1",
        target_classical_port: Optional[int] = None,
        target_optical_port: Optional[int] = None,
        esp32_port: Optional[str] = None,
        force_simulation: bool = False,
        target_port: Optional[int] = None,
        qber_baseline: Optional[float] = None,
        esp_port: Optional[str] = None,
        **kwargs,
    ):
        self.target_host = target_host
        self.target_classical_port = target_classical_port or target_port or DEFAULT_CLASSICAL_PORT
        self.target_optical_port = target_optical_port or ((target_port - 1) if target_port else DEFAULT_OPTICAL_PORT)
        self.force_simulation = force_simulation
        actual_esp = esp32_port or esp_port

        # Hardware interface
        self.esp32 = AttackerESP32Device(port=actual_esp)
        self.esp = self.esp32
        if not self.force_simulation:
            self.esp32.auto_detect_and_connect(preferred_port=actual_esp)

        # Dynamic Threshold Engine
        baseline = qber_baseline if qber_baseline is not None else 0.010
        self.threshold_engine = DynamicThresholdEngine(baseline_q0=baseline, alpha_traffic=0.012)

        # Telemetry & Stats
        self.stats = {
            "attacks_launched": 0,
            "packets_injected": 0,
            "bytes_transmitted": 0,
            "tampered_packets": 0,
            "last_attack_type": "None",
            "last_injected_qber": 0.0,
            "last_attack_time": None,
            "auto_attacks_count": 0,
            "captured_packets": [],
        }

        # UDP Socket for direct injection
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Rich Console
        self.console = Console() if HAS_RICH else None

        # Real-time MITM Proxy state
        self._proxy_running = False
        self._proxy_thread: Optional[threading.Thread] = None

        # Random In-Between Chat Auto-Attack state
        self.auto_attack_enabled = False
        self.auto_attack_min_interval = 8.0
        self.auto_attack_max_interval = 22.0
        self.auto_attack_rate = 0.35
        self._auto_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def compute_dynamic_qber(self, sample_size: int = 32, traffic_rate: float = 0.0) -> float:
        """Compute dynamic QBER threshold for a given sample size and traffic rate."""
        if hasattr(self.threshold_engine, "compute_threshold"):
            q_th, _ = self.threshold_engine.compute_threshold(sample_size_n=sample_size, traffic_rate_phi=traffic_rate)
            return q_th
        metrics = self.threshold_engine.compute_dynamic_threshold(sample_size=sample_size)
        return metrics.get("q_dyn", 0.06)

    def tamper_qubit_frame(self, raw_frame_bytes: bytes, error_rate: float = 0.5) -> bytes:
        """Directly tamper with raw optical qubit frames in flight."""
        try:
            data = json.loads(raw_frame_bytes.decode("utf-8"))
            if "payload" in data and isinstance(data["payload"], list):
                tampered = []
                for bit in data["payload"]:
                    if random.random() < error_rate:
                        tampered.append(1 - bit)
                    else:
                        tampered.append(bit)
                data["payload"] = tampered
                data["qubit_tampered"] = True
            if "c0" in data and random.random() < error_rate:
                data["c0"] = 1 - data["c0"]
            if "c1" in data and random.random() < error_rate:
                data["c1"] = 1 - data["c1"]
            return json.dumps(data).encode("utf-8")
        except Exception:
            return raw_frame_bytes

    def tamper_classical_packet(self, raw_packet_bytes: bytes, error_rate: float = 0.5) -> bytes:
        """Directly corrupt classical payload, MAC, or QDS in flight."""
        try:
            data = json.loads(raw_packet_bytes.decode("utf-8"))
            if "mac" in data:
                data["mac"] = "corrupted_" + data["mac"][:8]
            if "ciphertext" in data and data["ciphertext"]:
                ct = data["ciphertext"]
                flipped = "f" if ct[0] != "f" else "0"
                data["ciphertext"] = flipped + ct[1:]
            return json.dumps(data).encode("utf-8")
        except Exception:
            return raw_packet_bytes

    def attack_once(self, attack_type: str = "tamper", rate: float = 0.25) -> Dict[str, Any]:
        """Execute a single burst attack."""
        if attack_type in ("tamper", "tampering"):
            res = self.inject_pauli_tampering(flip_ratio=rate, target_role="Receiver")
            self.stats["tampered_packets"] = self.stats.get("tampered_packets", 0) + 1
            res["attack_type"] = "tamper"
            return res
        elif attack_type == "qber":
            res = self.inject_qber_disturbance(target_qber=rate, target_role="Receiver")
            res["attack_type"] = "qber"
            return res
        elif attack_type == "forgery":
            res = self.inject_forgery(target_role="Receiver")
            res["attack_type"] = "forgery"
            return res
        elif attack_type == "replay":
            res = self.inject_replay(target_role="Receiver")
            res["attack_type"] = "replay"
            return res
        elif attack_type == "jam":
            res = self.inject_jamming_burst(packet_count=15)
            res["attack_type"] = "jam"
            return res
        else:
            res = self.inject_qber_disturbance(target_qber=rate, target_role="Receiver")
            res["attack_type"] = attack_type
            return res

    def close(self):
        """Clean up threads, sockets, and hardware bridges."""
        self._stop_event.set()
        self.stop_random_attacks()
        self.stop_mitm_proxy()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self.esp32:
            self.esp32.disconnect()

    def _send_payload(self, packet: Dict[str, Any], port: Optional[int] = None) -> bool:
        """Send packet via UDP and optionally forward through Attacker ESP32 Wi-Fi."""
        target_port = port or self.target_classical_port
        raw_data = json.dumps(packet).encode("utf-8")

        success = False
        try:
            self._sock.sendto(raw_data, (self.target_host, target_port))
            self.stats["packets_injected"] += 1
            self.stats["bytes_transmitted"] += len(raw_data)
            success = True
        except Exception as e:
            logger.error("UDP injection error: %s", e)

        if self.esp32 and self.esp32.is_connected:
            self.esp32.transmit_wifi_packet(raw_data)

        return success

    # =========================================================================
    # ATTACK VECTOR 1: Quantum Channel Intercept-Resend & State Disturbance
    # =========================================================================
    def inject_qber_disturbance(
        self,
        message: str = "Intercepted quantum conversation",
        disturbance_rate: float = 0.35,
        target_role: str = "Receiver",
    ) -> Dict[str, Any]:
        """
        Simulate an Intercept-Resend / Quantum State Disturbance attack.
        Perturbs test qubits and Bell pairs using random noise generated by
        the Attacker ESP32's hardware TRNG.
        Forces Bob's calculated QBER to exceed the dynamic threshold,
        triggering message rejection and Bob's ESP32 threat alarm LED.
        """
        self.esp32.set_alarm(True, blink_ms=80)
        time.sleep(0.04)

        msg_bits = string_to_bits(message)
        data_count = len(msg_bits)

        c0_bits = []
        c1_bits = []
        bob_qubits = []

        for b in msg_bits:
            c0 = random.choice([0, 1])
            c1 = c0 ^ b
            c0_bits.append(c0)
            c1_bits.append(c1)
            bob_qubits.append(b)

        num_test = max(24, min(64, len(msg_bits) // 2))
        test_indices = list(range(data_count, data_count + num_test))
        test_values = []
        test_bases = []
        decoy_types = []

        # Get hardware entropy for disturbance
        trng = self.esp32.get_trng_bytes(num_test)
        disturbed_count = 0
        conclusive_mu = 0

        for i in range(num_test):
            tb = random.choice([0, 1])
            t_basis = random.choice(["Z", "X"])
            r_val = random.random()
            decoy = "mu" if r_val < 0.6 else ("nu" if r_val < 0.9 else "vac")

            # QBER disturbance injection
            is_disturbed = (trng[i % len(trng)] / 255.0) < disturbance_rate
            bob_bit = 1 - tb if is_disturbed else tb

            c0 = random.choice([0, 1])
            c1 = c0 ^ tb
            c0_bits.append(c0)
            c1_bits.append(c1)
            bob_qubits.append(bob_bit)

            test_values.append(tb)
            test_bases.append(t_basis)
            decoy_types.append(decoy)

            if decoy == "mu":
                conclusive_mu += 1
                if bob_bit != tb:
                    disturbed_count += 1

        injected_qber = (disturbed_count / conclusive_mu) if conclusive_mu > 0 else disturbance_rate
        dyn_metrics = self.threshold_engine.compute_dynamic_threshold(sample_size=max(16, conclusive_mu))
        dyn_th = dyn_metrics["q_dyn"]

        msg_id = "atk_qber_" + uuid.uuid4().hex[:8]

        # 1. Optical quantum burst with disturbed states
        optical_payload = {
            "msg_id": msg_id,
            "qubit_count": len(c0_bits),
            "data_qubits": data_count,
            "test_qubits": num_test,
            "basis": "Z",
            "bob_qubits": bob_qubits,
            "sender_optical_port": 9876,
        }
        raw_optical = json.dumps({"channel": "quantum_optical", "type": "TELEPORT_QUANTUM_BURST", "ts": time.time(), "payload": optical_payload}).encode("utf-8")
        try:
            self._sock.sendto(raw_optical, (self.target_host, self.target_optical_port))
        except Exception:
            pass

        # 2. Classical coordination packet
        classical_payload = {
            "msg_id": msg_id,
            "sender_role": "Peer A",
            "recipient": target_role,
            "text": message,
            "c0_bits": c0_bits,
            "c1_bits": c1_bits,
            "bob_qubits": bob_qubits,
            "data_bit_count": data_count,
            "test_indices": test_indices,
            "test_values": test_values,
            "test_bases": test_bases,
            "decoy_types": decoy_types,
            "attack": "intercept_resend",
            "sender_classical_port": 9877,
        }

        packet = {
            "channel": "classical_esp32",
            "type": "TELEPORT_MESSAGE",
            "ts": time.time(),
            "seq": self.stats["packets_injected"] + 1,
            "payload": classical_payload,
            "mac": "0123456789abcdef" * 4,
        }

        self._send_payload(packet, port=self.target_classical_port)
        self.stats["attacks_launched"] += 1
        self.stats["last_attack_type"] = "Quantum Intercept-Resend (QBER Injection)"
        self.stats["last_injected_qber"] = injected_qber
        self.stats["last_attack_time"] = time.time()

        self.esp32.set_alarm(False)

        return {
            "success": True,
            "attack": "intercept_resend",
            "msg_id": msg_id,
            "injected_qber": injected_qber,
            "target_dynamic_threshold": dyn_th,
            "disturbed_errors": disturbed_count,
            "conclusive_mu": conclusive_mu,
            "expected_outcome": f"REJECTED (DYNAMIC QBER THRESHOLD EXCEEDED) [QBER: {injected_qber*100:.1f}% > Q_th: {dyn_th*100:.2f}%]",
        }

    # =========================================================================
    # ATTACK VECTOR 2: Classical Pauli Coordinate Tampering
    # =========================================================================
    def inject_pauli_tampering(
        self,
        message: str = "Classically tampered transmission",
        flip_ratio: float = 0.40,
        target_role: str = "Receiver",
    ) -> Dict[str, Any]:
        """
        Invert c0/c1 Pauli coordinates in transit using ESP32 hardware TRNG.
        Causes misapplication of quantum bit-flip and phase-flip operators at Bob.
        """
        self.esp32.set_alarm(True, blink_ms=80)
        time.sleep(0.04)

        msg_bits = string_to_bits(message)
        data_count = len(msg_bits)

        c0_bits = [random.choice([0, 1]) for _ in range(data_count)]
        c1_bits = [c0 ^ b for c0, b in zip(c0_bits, msg_bits)]
        bob_qubits = list(msg_bits)

        # Invert c0 and c1 coordinates using Attacker ESP32 TRNG
        trng = self.esp32.get_trng_bytes(len(c0_bits))
        flipped = 0
        for i in range(len(c0_bits)):
            if (trng[i % len(trng)] / 255.0) < flip_ratio:
                c0_bits[i] = 1 - c0_bits[i]
                bob_qubits[i] = 1 - bob_qubits[i]
                flipped += 1

        msg_id = "atk_pauli_" + uuid.uuid4().hex[:8]
        payload = {
            "msg_id": msg_id,
            "sender_role": "Peer A",
            "recipient": target_role,
            "text": message,
            "c0_bits": c0_bits,
            "c1_bits": c1_bits,
            "bob_qubits": bob_qubits,
            "data_bit_count": data_count,
            "test_indices": [],
            "test_values": [],
            "test_bases": [],
            "decoy_types": [],
            "attack": "tampering",
            "sender_classical_port": 9877,
        }

        packet = {
            "channel": "classical_esp32",
            "type": "TELEPORT_MESSAGE",
            "ts": time.time(),
            "seq": self.stats["packets_injected"] + 1,
            "payload": payload,
            "mac": "0123456789abcdef" * 4,
        }

        self._send_payload(packet, port=self.target_classical_port)
        self.stats["attacks_launched"] += 1
        self.stats["last_attack_type"] = "Pauli Coordinate Tampering"
        self.stats["last_attack_time"] = time.time()

        self.esp32.set_alarm(False)
        return {
            "success": True,
            "attack": "tampering",
            "msg_id": msg_id,
            "flipped_bits": flipped,
            "total_qubits": len(c0_bits),
            "expected_outcome": "REJECTED (TAMPERING DETECTED / CORRUPTED PAULI FRAME)",
        }

    # =========================================================================
    # ATTACK VECTOR 3: Impersonation & Forgery Attack
    # =========================================================================
    def inject_forgery(
        self,
        fake_message: str = "UNAUTHORIZED OVERRIDE: TRANSFER ACCESS TO EVE",
        target_role: str = "Receiver",
        spoofed_sender: str = "Peer A",
    ) -> Dict[str, Any]:
        """
        Fabricate counterfeit message purporting to originate from Alice.
        Eve cannot compute the authentic Wegman-Carter MAC without the quantum key pool.
        The packet contains an invalid MAC token ('deadbeef...').
        """
        self.esp32.set_alarm(True, blink_ms=80)
        time.sleep(0.04)

        msg_bits = string_to_bits(fake_message)
        data_count = len(msg_bits)

        c0_bits = [random.choice([0, 1]) for _ in range(data_count)]
        c1_bits = [c0 ^ b for c0, b in zip(c0_bits, msg_bits)]
        bob_qubits = list(msg_bits)

        msg_id = "atk_forge_" + uuid.uuid4().hex[:8]
        forged_mac = "deadbeef" * 8

        payload = {
            "msg_id": msg_id,
            "sender_role": spoofed_sender,
            "recipient": target_role,
            "text": fake_message,
            "c0_bits": c0_bits,
            "c1_bits": c1_bits,
            "bob_qubits": bob_qubits,
            "data_bit_count": data_count,
            "test_indices": [],
            "test_values": [],
            "test_bases": [],
            "decoy_types": [],
            "attack": "forgery",
            "sender_classical_port": 9877,
        }

        packet = {
            "channel": "classical_esp32",
            "type": "TELEPORT_MESSAGE",
            "ts": time.time(),
            "seq": self.stats["packets_injected"] + 1,
            "payload": payload,
            "mac": forged_mac,
        }

        self._send_payload(packet, port=self.target_classical_port)
        self.stats["attacks_launched"] += 1
        self.stats["last_attack_type"] = "Impersonation / Forgery Attack"
        self.stats["last_attack_time"] = time.time()

        self.esp32.set_alarm(False)
        return {
            "success": True,
            "attack": "forgery",
            "msg_id": msg_id,
            "spoofed_sender": spoofed_sender,
            "forged_mac": forged_mac,
            "expected_outcome": "REJECTED (MAC VERIFICATION FAILED) -> Threat Alarm Triggered",
        }

    # =========================================================================
    # ATTACK VECTOR 4: Classical Replay Attack
    # =========================================================================
    def inject_replay(self, target_role: str = "Receiver") -> Dict[str, Any]:
        """Replay previously transmitted message with duplicate ID and stale timestamp."""
        self.esp32.set_alarm(True, blink_ms=80)
        time.sleep(0.04)

        stale_id = "msg_captured_replay_001"
        payload = {
            "msg_id": stale_id,
            "sender_role": "Peer A",
            "recipient": target_role,
            "text": "Stale repeated transmission payload",
            "c0_bits": [0, 1, 0, 1],
            "c1_bits": [1, 0, 1, 0],
            "bob_qubits": [1, 1, 1, 1],
            "data_bit_count": 4,
            "test_indices": [],
            "test_values": [],
            "test_bases": [],
            "decoy_types": [],
            "attack": "replay",
            "sender_classical_port": 9877,
        }

        packet = {
            "channel": "classical_esp32",
            "type": "TELEPORT_MESSAGE",
            "ts": time.time() - 7200.0,
            "seq": 1,
            "payload": payload,
            "mac": "deadbeef" * 8,
        }

        self._send_payload(packet, port=self.target_classical_port)
        self.stats["attacks_launched"] += 1
        self.stats["last_attack_type"] = "Classical Replay Attack"
        self.stats["last_attack_time"] = time.time()

        self.esp32.set_alarm(False)
        return {
            "success": True,
            "attack": "replay",
            "stale_id": stale_id,
            "expected_outcome": "REJECTED (DUPLICATE MSG_ID FILTERED OR STALE KEY BURN)",
        }

    # =========================================================================
    # ATTACK VECTOR 5: Hardware TRNG Jamming Burst
    # =========================================================================
    def inject_jamming_burst(self, packet_count: int = 20, delay: float = 0.04) -> Dict[str, Any]:
        """Flood classical UDP channel with rapid random noise frames using ESP32 TRNG."""
        self.esp32.set_alarm(True, blink_ms=50)

        # Trigger hardware jamming on ESP32 directly if connected
        if self.esp32.is_connected:
            self.esp32.trigger_jamming(count=packet_count, delay_ms=int(delay * 1000))

        sent = 0
        for _ in range(packet_count):
            noise_bytes = self.esp32.get_trng_bytes(48)
            jam_packet = {
                "channel": "classical_esp32",
                "type": "CHANNEL_JAM_BURST",
                "ts": time.time(),
                "entropy_noise": noise_bytes.hex(),
            }
            self._send_payload(jam_packet, port=self.target_classical_port)
            sent += 1
            time.sleep(delay)

        self.esp32.set_alarm(False)
        self.stats["attacks_launched"] += 1
        self.stats["last_attack_type"] = "Hardware Jamming Burst"
        self.stats["last_attack_time"] = time.time()

        return {
            "success": True,
            "attack": "jamming",
            "packets_sent": sent,
            "expected_outcome": "Channel Congestion & Handshake Synchronization Interference",
        }

    # =========================================================================
    # RANDOM IN-BETWEEN CHAT AUTO-ATTACK ENGINE
    # =========================================================================
    def start_random_attacks(
        self,
        min_interval: float = 8.0,
        max_interval: float = 22.0,
        disturbance_rate: float = 0.35,
    ):
        """
        Start background auto-attack thread.
        Randomly attacks the communication channel in-between chat messages
        to tamper with conversations and trigger dynamic QBER security alarms.
        """
        if self.auto_attack_enabled:
            return

        self.auto_attack_enabled = True
        self.auto_attack_min_interval = max(3.0, min_interval)
        self.auto_attack_max_interval = max(self.auto_attack_min_interval, max_interval)
        self.auto_attack_rate = disturbance_rate

        def auto_loop():
            while self.auto_attack_enabled and not self._stop_event.is_set():
                sleep_time = random.uniform(self.auto_attack_min_interval, self.auto_attack_max_interval)
                t_end = time.time() + sleep_time
                while time.time() < t_end:
                    if not self.auto_attack_enabled or self._stop_event.is_set():
                        return
                    time.sleep(0.5)

                if not self.auto_attack_enabled or self._stop_event.is_set():
                    break

                # Pick randomized attack vector
                vector_choice = random.choices(
                    ["qber", "pauli", "forge", "replay", "jam"],
                    weights=[0.45, 0.25, 0.15, 0.05, 0.10],
                    k=1
                )[0]

                try:
                    if vector_choice == "qber":
                        res = self.inject_qber_disturbance(
                            message=f"Stealth quantum disturbance #{self.stats['auto_attacks_count']+1}",
                            disturbance_rate=self.auto_attack_rate,
                        )
                        self._render_auto_attack_notification("Quantum Intercept-Resend (QBER Injection)", f"QBER: {res['injected_qber']*100:.1f}% > Q_th {res['target_dynamic_threshold']*100:.2f}%")

                    elif vector_choice == "pauli":
                        res = self.inject_pauli_tampering(
                            message=f"Stealth Pauli Inversion #{self.stats['auto_attacks_count']+1}",
                            flip_ratio=0.40,
                        )
                        self._render_auto_attack_notification("Pauli Coordinate Tampering", f"Flipped {res['flipped_bits']} transit coordinates")

                    elif vector_choice == "forge":
                        res = self.inject_forgery(
                            fake_message=f"Counterfeit Injection #{self.stats['auto_attacks_count']+1}",
                        )
                        self._render_auto_attack_notification("Wegman-Carter MAC Forgery", "Injected bogus MAC 'deadbeef...'")

                    elif vector_choice == "replay":
                        res = self.inject_replay()
                        self._render_auto_attack_notification("Classical Replay Attack", f"Replayed stale packet: {res['stale_id']}")

                    elif vector_choice == "jam":
                        res = self.inject_jamming_burst(packet_count=12)
                        self._render_auto_attack_notification("TRNG Channel Jamming", f"Blasted {res['packets_sent']} noise packets")

                    self.stats["auto_attacks_count"] += 1
                except Exception as e:
                    logger.debug("Auto-attack loop exception: %s", e)

        self._auto_thread = threading.Thread(target=auto_loop, daemon=True)
        self._auto_thread.start()

    def stop_random_attacks(self):
        """Stop background random auto-attack engine."""
        self.auto_attack_enabled = False
        if self._auto_thread:
            self._auto_thread.join(timeout=1.0)
            self._auto_thread = None

    def _render_auto_attack_notification(self, attack_name: str, detail: str):
        """Render discrete adversary auto-attack alert."""
        if HAS_RICH and self.console:
            t = time.strftime("%H:%M:%S")
            self.console.print(f"[dim]{t}[/dim] [bold red]⚡ [AUTO-ATTACK][/bold red] [cyan]{attack_name}[/cyan] · [yellow]{detail}[/yellow]")
            print("❯ ", end="", flush=True)
        else:
            t = time.strftime("%H:%M:%S")
            print(f"\n[{t}] ⚡ [AUTO-ATTACK] {attack_name}: {detail}")
            print("❯ ", end="", flush=True)

    # =========================================================================
    # REAL-TIME MAN-IN-THE-MIDDLE (MITM) PROXY & SNIFFER
    # =========================================================================
    def start_mitm_proxy(
        self,
        listen_port: int = 9880,
        forward_host: str = "127.0.0.1",
        forward_port: int = DEFAULT_CLASSICAL_PORT,
        auto_tamper: bool = False,
    ):
        """Start real-time MITM listener and transparent proxy."""
        if self._proxy_running:
            return

        self._proxy_running = True

        def proxy_loop():
            proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            proxy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                proxy_sock.bind(("0.0.0.0", listen_port))
                proxy_sock.settimeout(0.5)
                if HAS_RICH and self.console:
                    self.console.print(f"[bold cyan]╭─ MITM Proxy Online ────────────────────────────────────────────────╮[/bold cyan]")
                    self.console.print(f"[bold cyan]│[/bold cyan] Listening: [bold white]0.0.0.0:{listen_port}[/bold white] ➔ Forwarding: [bold white]{forward_host}:{forward_port}[/bold white]")
                    self.console.print(f"[bold cyan]│[/bold cyan] Auto-Tampering: [bold {'red' if auto_tamper else 'yellow'}]{'ENABLED (Inverting Qubits in Transit)' if auto_tamper else 'SNIFFER ONLY'}[/bold {'red' if auto_tamper else 'yellow'}]")
                    self.console.print(f"[bold cyan]╰────────────────────────────────────────────────────────────────────╯[/bold cyan]")
            except Exception as e:
                self._proxy_running = False
                return

            while self._proxy_running:
                try:
                    data, addr = proxy_sock.recvfrom(65535)
                    pkt = json.loads(data.decode("utf-8"))
                    self.stats["captured_packets"].append(pkt)

                    p_type = pkt.get("type", "UNKNOWN")
                    sender = pkt.get("payload", {}).get("sender_role", "Unknown")
                    msg_text = pkt.get("payload", {}).get("text", "<qubit-teleportation>")

                    if HAS_RICH and self.console:
                        self.console.print(f"[magenta]◈ [INTERCEPTED][/magenta] From [white]{addr[0]}:{addr[1]}[/white] | Type: [yellow]{p_type}[/yellow] | Sender: [cyan]{sender}[/cyan] | \"[white]{msg_text}[/white]\"")

                    if auto_tamper and p_type == "TELEPORT_MESSAGE":
                        payload = pkt.get("payload", {})
                        if "bob_qubits" in payload and payload["bob_qubits"]:
                            payload["bob_qubits"][0] = 1 - payload["bob_qubits"][0]
                            payload["attack"] = "tampering"
                        if HAS_RICH and self.console:
                            self.console.print(f"  [bold red]↳ [TAMPERED] Injected state error into qubit 0 via ESP32 TRNG![/bold red]")

                    forward_bytes = json.dumps(pkt).encode("utf-8")
                    self._sock.sendto(forward_bytes, (forward_host, forward_port))
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.debug("Proxy loop exception: %s", e)

            proxy_sock.close()

        self._proxy_thread = threading.Thread(target=proxy_loop, daemon=True)
        self._proxy_thread.start()

    def stop_mitm_proxy(self):
        """Stop background MITM proxy."""
        self._proxy_running = False
        if self._proxy_thread:
            self._proxy_thread.join(timeout=1.0)
            self._proxy_thread = None

    # =========================================================================
    # ADVERSARY TUI DASHBOARDS & RENDERING
    # =========================================================================
    def render_adversary_banner(self):
        """Render adversary header container."""
        if not (HAS_RICH and self.console):
            print("\n=== QUSEC ADVERSARY SUITE (EVE) ===")
            print(f"Target: {self.target_host}:{self.target_classical_port}")
            return

        hw_tag = f"[bold green]{self.esp32.port}[/bold green]" if self.esp32.is_connected else "[bold yellow]Simulated[/bold yellow]"
        auto_tag = f"[bold red]ACTIVE (Interval: {self.auto_attack_min_interval:.0f}-{self.auto_attack_max_interval:.0f}s)[/bold red]" if self.auto_attack_enabled else "[dim]Disabled (Use /random on)[/dim]"
        mitm_tag = "[bold red]ACTIVE[/bold red]" if self._proxy_running else "[dim]Idle[/dim]"

        dyn_th = self.threshold_engine.compute_dynamic_threshold(sample_size=32)["q_dyn"]

        banner_text = (
            f"[bold red]QuSec Attacker · Eve[/bold red]  [dim]v2.5.0 · Adversary Cyber Threat Suite[/dim]\n\n"
            f"  [cyan]◈ Target Host:[/cyan]       [white]{self.target_host}[/white]  [dim](Classical: {self.target_classical_port} · Optical: {self.target_optical_port})[/dim]\n"
            f"  [cyan]◈ Attacker ESP32:[/cyan]    {hw_tag}  [dim](Hardware TRNG & Pin 4 LED)[/dim]\n"
            f"  [cyan]◈ Dynamic Q_th:[/cyan]      [bold magenta]{dyn_th * 100:.2f}%[/bold magenta]  [dim](Mathematical Auto-Adjusting Engine)[/dim]\n"
            f"  [cyan]◈ Auto-Attack:[/cyan]       {auto_tag}\n"
            f"  [cyan]◈ MITM Proxy:[/cyan]        {mitm_tag}  [dim](In-Flight Real-Time Packet Tamperer)[/dim]\n"
            f"  [cyan]◈ Attacks Total:[/cyan]     [bold white]{self.stats['attacks_launched']}[/bold white]  [dim](Packets Injected: {self.stats['packets_injected']})[/dim]"
        )

        p = Panel(
            banner_text,
            title="[bold red]╭─ Adversary Environment ─╮[/bold red]",
            subtitle="[dim]Type /help for slash commands · /attack for threat vectors[/dim]",
            box=box.ROUNDED,
            border_style="bright_black",
            padding=(1, 2),
        )
        self.console.print(p)

    def render_attack_card(self, title: str, details: Dict[str, Any]):
        """Render attack execution card."""
        if not (HAS_RICH and self.console):
            print(f"\n--- {title} ---")
            for k, v in details.items():
                print(f"  {k}: {v}")
            return

        body_lines = []
        for k, v in details.items():
            key_label = k.replace("_", " ").title()
            val_str = str(v)
            if "REJECTED" in val_str or "EXCEEDED" in val_str:
                val_formatted = f"[bold red]{val_str}[/bold red]"
            elif "VERIFIED" in val_str or "True" in val_str:
                val_formatted = f"[bold green]{val_str}[/bold green]"
            elif isinstance(v, float) and v < 1.0:
                val_formatted = f"[bold yellow]{v*100:.1f}%[/bold yellow]"
            else:
                val_formatted = f"[white]{val_str}[/white]"
            body_lines.append(f"  [cyan]{key_label:26}[/cyan] {val_formatted}")

        panel_content = "\n".join(body_lines)
        p = Panel(
            panel_content,
            title=f"[bold red]╭─ ⚡ Threat Vector: {title} ─╮[/bold red]",
            box=box.ROUNDED,
            border_style="red",
            padding=(0, 1),
        )
        self.console.print(p)

    def print_help(self):
        """Display adversary command guide."""
        if not (HAS_RICH and self.console):
            print("\nAvailable Commands:")
            print("  /attack <type>   - Inject attack: tamper, pauli, forge, replay, jam")
            print("  /random <on|off> - Automated stealth attacks in-between chats")
            print("  /mitm <start|stop> - Transparent proxy & in-flight packet tamper")
            print("  /target <ip> [port] - Change target node IP / port")
            print("  /threshold       - View target's dynamic QBER threshold math")
            print("  /hardware        - Test Attacker ESP32 hardware & Pin 4 LED")
            print("  /stats           - View adversary telemetry table")
            print("  /clear           - Clear terminal")
            print("  /exit            - Quit adversary suite\n")
            return

        table = Table(box=box.ROUNDED, border_style="bright_black", show_header=True, header_style="bold cyan")
        table.add_column("Command / Slash", style="bold yellow", width=22)
        table.add_column("Description", style="white")

        table.add_row("/attack [vector]", "Execute specific attack: tamper (qber), pauli, forge, replay, jam")
        table.add_row("/random [on|off]", "Automated stealth attacks in-between chats (Random interval 8-22s)")
        table.add_row("/mitm [start|stop]", "Transparent proxy sniffing and in-flight qubit flipping")
        table.add_row("/target <ip> [port]", "Set target Receiver IP and Classical UDP Port")
        table.add_row("/threshold", "Inspect target's Dynamic QBER Threshold & Raman scattering model")
        table.add_row("/hardware", "Test Attacker ESP32 True Random Entropy (esp_random) & LED Strobe")
        table.add_row("/stats", "Display full attack telemetry and injected packet counters")
        table.add_row("/clear", "Clear the terminal screen")
        table.add_row("/help", "Show this command reference")
        table.add_row("/exit, /quit", "Gracefully terminate adversary engine")

        p = Panel(table, title="[bold cyan]╭─ QuSec Adversary Commands ─╮[/bold cyan]", box=box.ROUNDED, border_style="cyan")
        self.console.print(p)

    def run_interactive(self):
        """Run interactive adversary CLI loop."""
        if os.name != "nt":
            os.system("clear")
        else:
            os.system("cls")

        self.render_adversary_banner()

        while True:
            try:
                if HAS_RICH and self.console:
                    prompt_str = "[bold red]╭─[/bold red] [dim]qusec-attacker[/dim] [bold red]──[/bold red]\n[bold red]╰─ ❯[/bold red] "
                    self.console.print(prompt_str, end="")
                    user_input = input().strip()
                else:
                    user_input = input("Eve-Attacker ❯ ").strip()

                if not user_input:
                    continue

                parts = user_input.split()
                cmd = parts[0].lower()
                arg1 = parts[1] if len(parts) > 1 else ""
                arg2 = parts[2] if len(parts) > 2 else ""

                if cmd in ("/exit", "/quit", "exit", "quit", "q", "0"):
                    if HAS_RICH and self.console:
                        self.console.print("[yellow]Shutting down QuSec Adversary Suite...[/yellow]")
                    break

                elif cmd in ("/help", "help", "?"):
                    self.print_help()

                elif cmd in ("/clear", "clear", "cls"):
                    if os.name != "nt":
                        os.system("clear")
                    else:
                        os.system("cls")
                    self.render_adversary_banner()

                elif cmd in ("/attack", "attack", "1", "2", "3", "4", "5", "6"):
                    # Resolve vector
                    sub_cmd = arg1.lower() if arg1 else cmd
                    if sub_cmd in ("1", "tamper", "qber", "intercept"):
                        res = self.inject_qber_disturbance(message="Quantum channel intercept simulation", disturbance_rate=0.35)
                        self.render_attack_card("Quantum Intercept-Resend (QBER Injection)", res)
                    elif sub_cmd in ("2", "pauli", "coord"):
                        res = self.inject_pauli_tampering(message="Secret Pauli Teleportation", flip_ratio=0.40)
                        self.render_attack_card("Classical Pauli Coordinate Tampering", res)
                    elif sub_cmd in ("3", "forge", "mac"):
                        res = self.inject_forgery(fake_message="UNAUTHORIZED OVERRIDE: TRANSFER ASSETS TO EVE")
                        self.render_attack_card("Impersonation & Wegman-Carter MAC Forgery", res)
                    elif sub_cmd in ("4", "replay"):
                        res = self.inject_replay()
                        self.render_attack_card("Classical Stale Replay Attack", res)
                    elif sub_cmd in ("5", "jam", "flood"):
                        res = self.inject_jamming_burst(packet_count=20)
                        self.render_attack_card("Hardware TRNG Channel Jamming Burst", res)
                    else:
                        if HAS_RICH and self.console:
                            self.console.print("[bold red]Unknown attack vector.[/bold red] Options: [yellow]tamper, pauli, forge, replay, jam[/yellow]")

                elif cmd in ("/random", "random", "auto"):
                    sub_cmd = arg1.lower()
                    if sub_cmd in ("on", "start", "enable", "1"):
                        self.start_random_attacks()
                        if HAS_RICH and self.console:
                            self.console.print(f"[bold green]✔ In-Between Chat Auto-Attack ACTIVE![/bold green] [dim]Blasting random attacks every {self.auto_attack_min_interval:.0f}-{self.auto_attack_max_interval:.0f}s while users chat.[/dim]")
                    elif sub_cmd in ("off", "stop", "disable", "0"):
                        self.stop_random_attacks()
                        if HAS_RICH and self.console:
                            self.console.print("[yellow]In-Between Chat Auto-Attack DISABLED.[/yellow]")
                    else:
                        status_str = "[bold green]ACTIVE[/bold green]" if self.auto_attack_enabled else "[dim]DISABLED[/dim]"
                        if HAS_RICH and self.console:
                            self.console.print(f"Auto-Attack Status: {status_str} (Interval: {self.auto_attack_min_interval:.0f}-{self.auto_attack_max_interval:.0f}s, Injected: {self.stats['auto_attacks_count']})")
                            self.console.print("[dim]Use '/random on' to enable, '/random off' to disable[/dim]")

                elif cmd in ("/mitm", "mitm", "proxy"):
                    sub_cmd = arg1.lower()
                    if sub_cmd in ("stop", "off", "disable", "0"):
                        self.stop_mitm_proxy()
                        if HAS_RICH and self.console:
                            self.console.print("[yellow]MITM Proxy stopped.[/yellow]")
                    else:
                        tamper_mode = (arg2.lower() in ("tamper", "true", "on", "1"))
                        self.start_mitm_proxy(
                            listen_port=9880,
                            forward_host=self.target_host,
                            forward_port=self.target_classical_port,
                            auto_tamper=tamper_mode,
                        )

                elif cmd in ("/target", "target"):
                    if arg1:
                        self.target_host = arg1
                    if arg2 and arg2.isdigit():
                        self.target_classical_port = int(arg2)
                    if HAS_RICH and self.console:
                        self.console.print(f"[bold green]✔ Target updated:[/bold green] [white]{self.target_host}:{self.target_classical_port}[/white]")

                elif cmd in ("/threshold", "threshold", "dyn"):
                    dyn = self.threshold_engine.compute_dynamic_threshold(sample_size=32)
                    if HAS_RICH and self.console:
                        t = Table(title="[bold magenta]Dynamic QBER Threshold Model[/bold magenta]", box=box.ROUNDED)
                        t.add_column("Parameter", style="cyan")
                        t.add_column("Value", style="yellow")
                        t.add_row("Dynamic Q_th", f"{dyn['q_dyn']*100:.2f}% (Auto-Adjusted)")
                        t.add_row("Static Baseline (Q0)", f"{dyn['baseline_q0']*100:.2f}%")
                        t.add_row("Security Floor (Q_floor)", f"{dyn['q_floor']*100:.2f}%")
                        t.add_row("Ceiling (Q_ceiling)", f"{dyn['q_ceiling']*100:.2f}%")
                        t.add_row("Traffic Noise Penalty", f"{dyn['delta_traffic']*100:.2f}%")
                        t.add_row("Finite Statistical Fluctuation", f"{dyn['delta_stat']*100:.2f}%")
                        self.console.print(t)

                elif cmd in ("/hardware", "hardware", "7"):
                    diag = {
                        "ESP32 Connected": self.esp32.is_connected,
                        "Serial Port": self.esp32.port or "Simulated",
                        "Firmware": self.esp32.firmware_version,
                        "Hardware TRNG Sample": self.esp32.get_trng_bytes(16).hex(),
                    }
                    if self.esp32.is_connected:
                        self.esp32.set_alarm(True, blink_ms=100)
                        time.sleep(0.3)
                        self.esp32.set_alarm(False)
                        diag["Pin 4 LED Strobe"] = "Verified"
                    self.render_attack_card("Attacker ESP32 Hardware Status", diag)

                elif cmd in ("/stats", "/dash", "stats", "status"):
                    self.render_adversary_banner()

                else:
                    if HAS_RICH and self.console:
                        self.console.print(f"[bold red]Unknown command:[/bold red] '{cmd}'. Type [bold cyan]/help[/bold cyan] for commands.")

            except (KeyboardInterrupt, EOFError):
                if HAS_RICH and self.console:
                    self.console.print("\n[yellow]Interrupted by user. Exiting adversary suite...[/yellow]")
                break

        self.close()


def main():
    """CLI entry point for qusec-attacker."""
    parser = argparse.ArgumentParser(
        prog="qusec-attacker",
        description="QuSec Adversary & Threat Vector Demonstration Suite (Eve)",
    )
    parser.add_argument("--target-host", default="127.0.0.1", help="Target Receiver IP (default: 127.0.0.1 or 192.168.4.2)")
    parser.add_argument("--target-classical-port", type=int, default=DEFAULT_CLASSICAL_PORT, help="Target classical UDP port (default: 9877, or 9879 for Bob)")
    parser.add_argument("--target-optical-port", type=int, default=DEFAULT_OPTICAL_PORT, help="Target optical UDP port (default: 9876, or 9878 for Bob)")
    parser.add_argument("--esp32-port", default=None, help="Attacker ESP32 serial port (e.g. COM5 or /dev/ttyUSB*)")
    parser.add_argument("--sim", action="store_true", help="Force software simulation mode (no physical ESP32)")
    parser.add_argument("--attack", choices=["tamper", "intercept_resend", "pauli", "forge", "replay", "jam"], default=None, help="Execute specific attack non-interactively")
    parser.add_argument("--random", action="store_true", help="Launch directly into automated random in-between chat attack mode")
    parser.add_argument("--message", default="Quantum attack simulation", help="Message payload for attack")
    parser.add_argument("--rate", type=float, default=0.35, help="Disturbance / flip error rate (default: 0.35)")

    args = parser.parse_args()

    attacker = QuSecAttacker(
        target_host=args.target_host,
        target_classical_port=args.target_classical_port,
        target_optical_port=args.target_optical_port,
        esp32_port=args.esp32_port,
        force_simulation=args.sim,
    )

    if args.attack:
        if args.attack in ("tamper", "intercept_resend"):
            res = attacker.inject_qber_disturbance(message=args.message, disturbance_rate=args.rate)
            print(json.dumps(res, indent=2))
        elif args.attack == "pauli":
            res = attacker.inject_pauli_tampering(message=args.message, flip_ratio=args.rate)
            print(json.dumps(res, indent=2))
        elif args.attack == "forge":
            res = attacker.inject_forgery(fake_message=args.message)
            print(json.dumps(res, indent=2))
        elif args.attack == "replay":
            res = attacker.inject_replay()
            print(json.dumps(res, indent=2))
        elif args.attack == "jam":
            res = attacker.inject_jamming_burst(packet_count=20)
            print(json.dumps(res, indent=2))
        attacker.close()
        return 0

    if args.random:
        attacker.start_random_attacks(min_interval=8.0, max_interval=20.0, disturbance_rate=args.rate)

    attacker.run_interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
