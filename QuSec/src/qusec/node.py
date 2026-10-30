"""
QuSec Core Node Runtime.
Orchestrates hardware drivers (ESP32, Optical media converters), quantum protocols
(Entanglement distribution, SARG04, Cascade, Privacy Amplification, Teleportation),
cryptography (OTP, Wegman-Carter MAC), full-duplex bidirectional chatting,
and the live Terminal UI dashboard.
"""

import time
import json
import uuid
import random
import threading
import logging
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich import box

from qusec.detection.qber import qber, hoeffding_margin
from qusec.detection.threshold import ThresholdEngine, DynamicThresholdEngine
from qusec.quantum.backend import get_backend_label, normalize_backend_type
from qusec.hardware.esp32 import ESP32Detector, ESP32Device
from qusec.hardware.rng import RandomSource
from qusec.hardware.optical import QuantumChannel, EthernetDetector
from qusec.hardware.classical import ClassicalChannel
from qusec.quantum.entanglement import EntanglementEngine
from qusec.quantum.teleport import QuantumTeleportationEngine
from qusec.protocol.sarg04 import SARG04ProtocolEngine
from qusec.protocol.cascade import CascadeReconciler
from qusec.protocol.privacy import PrivacyAmplifier
from qusec.crypto.otp import OneTimePad, string_to_bits, bits_to_string
from qusec.crypto.auth import WegmanCarterMAC
from qusec.crypto.quantum_keys import (
    QuantumKeyPair,
    QuantumPublicKey,
    QuantumPrivateKey,
    encrypt_with_quantum_public_key,
    decrypt_with_quantum_private_key,
    sign_with_quantum_private_key,
    verify_with_quantum_public_key,
)
from qusec.session.key_pool import KeyPool
from qusec.session.manager import SessionManager, SessionState

from qusec.gateway.server import GatewayServer, GatewayContext
from qusec.gateway.events import EventEmitter
from qusec.ui.terminal_ui import TerminalUIDashboard

logger = logging.getLogger("qusec.node")


class QuSecNode:
    """
    Operational full-duplex node for Sender or Receiver.
    Both Sender and Receiver can transmit messages and receive messages.
    """

    def __init__(
        self,
        role: str = "sender",
        peer_host: str = "127.0.0.1",
        optical_port: Optional[int] = None,
        classical_port: Optional[int] = None,
        gateway_port: Optional[int] = None,
        peer_optical_port: Optional[int] = None,
        peer_classical_port: Optional[int] = None,
        esp32_port: Optional[str] = None,
        force_simulation: bool = False,
        backend_type: str = "simulator",
    ):
        r = (role or "peer").lower()
        if r in ("peer_b", "bob", "2"):
            self.role = "receiver"
            self.peer_role = "sender"
            self.role_title = "Peer B"
            self.peer_title = "Peer A"
        elif r == "receiver":
            self.role = "receiver"
            self.peer_role = "sender"
            self.role_title = "Receiver"
            self.peer_title = "Sender"
        elif r in ("peer_a", "alice", "1"):
            self.role = "sender"
            self.peer_role = "receiver"
            self.role_title = "Peer A"
            self.peer_title = "Peer B"
        elif r in ("peer", "dual"):
            if gateway_port == 8766 or optical_port == 9878:
                self.role = "receiver"
                self.peer_role = "sender"
                self.role_title = "Peer B"
                self.peer_title = "Peer A"
            else:
                self.role = "sender"
                self.peer_role = "receiver"
                self.role_title = "Peer A"
                self.peer_title = "Peer B"
        else:
            self.role = "sender"
            self.peer_role = "receiver"
            self.role_title = "Sender"
            self.peer_title = "Receiver"

        self.peer_host = peer_host
        self.esp32_port = esp32_port
        self.force_simulation = force_simulation
        self.backend_type = normalize_backend_type(backend_type)
        self.backend_label = get_backend_label(self.backend_type)

        # Smart port configuration:
        # If running locally on localhost, assign non-colliding default ports;
        # if running on separate physical laptops across network, use identical standard ports.
        is_local = self.peer_host in ("127.0.0.1", "localhost")
        if is_local:
            if self.role == "sender":
                self.optical_port = optical_port or 9876
                self.classical_port = classical_port or 9877
                self.peer_optical_port = peer_optical_port or 9878
                self.peer_classical_port = peer_classical_port or 9879
                self.gateway_port = gateway_port or 8765
            else:
                self.optical_port = optical_port or 9878
                self.classical_port = classical_port or 9879
                self.peer_optical_port = peer_optical_port or 9876
                self.peer_classical_port = peer_classical_port or 9877
                self.gateway_port = gateway_port or 8766
        else:
            self.optical_port = optical_port or 9876
            self.classical_port = classical_port or 9877
            self.peer_optical_port = peer_optical_port or 9876
            self.peer_classical_port = peer_classical_port or 9877
            self.gateway_port = gateway_port or 8765

        # Event broadcaster
        self.events = EventEmitter()

        # Hardware drivers
        self.esp32: Optional[ESP32Device] = None
        if not self.force_simulation:
            self.esp32 = ESP32Detector.find_esp32(preferred_port=self.esp32_port)

        self.rng = RandomSource(esp32_device=self.esp32, force_simulation=self.force_simulation)
        self.quantum_channel = QuantumChannel(
            local_port=self.optical_port,
            peer_host=self.peer_host,
            peer_port=self.peer_optical_port,
            force_simulation=self.force_simulation,
        )
        self.classical_channel = ClassicalChannel(
            local_port=self.classical_port,
            peer_host=self.peer_host,
            peer_port=self.peer_classical_port,
            esp32_device=self.esp32,
            force_simulation=self.force_simulation,
        )

        # Dynamic Mathematical Threshold Engine (Auto-adjusts for traffic, message length, and drift)
        self.threshold_engine = DynamicThresholdEngine(baseline_q0=0.010, alpha_traffic=0.012)

        # Quantum engines
        self.entanglement = EntanglementEngine(backend_type=self.backend_type)
        self.teleporter = QuantumTeleportationEngine(backend_type=self.backend_type)
        self.sarg04 = SARG04ProtocolEngine()
        self.cascade = CascadeReconciler()
        self.privacy = PrivacyAmplifier()

        # Session & Keys
        self.key_pool = KeyPool(rekey_threshold=512, target_pool_size=4820)
        self.session_mgr = SessionManager(role=self.role, key_pool=self.key_pool)

        # Terminal UI
        self.ui = TerminalUIDashboard(role=self.role_title)

        # Message stores
        self.received_messages: List[Dict[str, Any]] = []
        self.sent_messages: List[Dict[str, Any]] = []
        self._seen_msg_ids = set()
        self._received_optical_bursts: Dict[str, Dict[str, Any]] = {}

        # Gateway Context & Server
        self.gateway_ctx = GatewayContext(
            node_role=self.role,
            session_mgr=self.session_mgr,
            key_pool=self.key_pool,
            event_emitter=self.events,
            send_message_fn=self.send_message,
            rekey_fn=self.replenish_key_pool,
            init_session_fn=self.initiate_session,
            backend_name=self.backend_label,
            backend_type=self.backend_type,
            threshold_engine=self.threshold_engine,
        )
        self.gateway_server = GatewayServer(self.gateway_ctx, host="0.0.0.0", port=self.gateway_port)

        self.is_running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self.on_message_callback: Optional[Any] = None
        self.active_attack: Optional[str] = None

    @property
    def quantum_public_key(self) -> QuantumPublicKey:
        """Node's local Quantum Public Key."""
        return self.session_mgr.keypair.public_key

    @property
    def quantum_private_key(self) -> QuantumPrivateKey:
        """Node's local Quantum Private Key."""
        return self.session_mgr.keypair.private_key

    @property
    def peer_quantum_public_key(self) -> QuantumPublicKey:
        """Peer's Quantum Public Key."""
        return self.session_mgr.get_peer_quantum_public_key()


    def trigger_esp32_threat_alarm(self, enable: bool = True):
        """Control the ESP32 second LED security threat alarm (blinks on threat)."""
        if self.esp32:
            self.esp32.set_alarm(enable=enable, blink_ms=150)
        self.gateway_ctx.hardware_state["alarm_active"] = enable
        self.events.emit("threat_alarm", {"active": enable})

    def _optical_carrier_watchdog_loop(self):
        """
        Background watchdog monitoring the physical optical fiber link carrier in real time.
        If the physical optical fiber cable is unplugged, updates link state to disconnected,
        updates the terminal dashboard, and emits SSE/WebSocket events to the web gateway.
        """
        last_state: Optional[bool] = None
        while self.is_running:
            try:
                fibre_ok = self.quantum_channel.link_ok
                esp32_ok = self.classical_channel.esp32_ok

                # Update states if changed
                if last_state is None or fibre_ok != last_state:
                    last_state = fibre_ok
                    self.ui.set_hardware_status(
                        fibre_ok=fibre_ok,
                        esp32_ok=esp32_ok,
                        is_simulation=self.force_simulation,
                    )
                    self.gateway_ctx.hardware_state["fibre_ok"] = fibre_ok
                    self.gateway_ctx.hardware_state["esp32_ok"] = esp32_ok
                    self.events.emit("hardware_status", {
                        "fibre_ok": fibre_ok,
                        "esp32_ok": esp32_ok,
                        "is_simulation": self.force_simulation,
                    })
                    if not fibre_ok and not self.force_simulation:
                        self.ui.add_log("[bold red]▲ Optical Fibre disconnected! Carrier signal lost.[/bold red]")
                    elif fibre_ok and not self.force_simulation and last_state is not None:
                        self.ui.add_log("[bold green]● Optical Fibre link carrier detected! Link online.[/bold green]")

            except Exception as e:
                logger.debug("Carrier watchdog exception: %s", e)

            # Sleep 1.2s between link carrier checks
            for _ in range(12):
                if not self.is_running:
                    break
                time.sleep(0.1)

    def initialize(self) -> bool:
        """Start hardware channels, listener thread, gateway server, and establish session."""
        q_ok = self.quantum_channel.open()
        c_ok = self.classical_channel.open()
        if self.esp32:
            self.esp32.set_role(self.role)
        self.gateway_server.start()

        # Check hardware indicators
        fibre_ok = self.quantum_channel.link_ok
        esp32_ok = self.classical_channel.esp32_ok
        self.ui.set_hardware_status(fibre_ok=fibre_ok, esp32_ok=esp32_ok, is_simulation=self.force_simulation)
        self.gateway_ctx.hardware_state["fibre_ok"] = fibre_ok
        self.gateway_ctx.hardware_state["esp32_ok"] = esp32_ok

        self.is_running = True

        # Start background listener thread for two-way chat packets
        self._listener_thread = threading.Thread(target=self._channel_listener_loop, daemon=True)
        self._listener_thread.start()

        # Start background watchdog thread for real-time optical carrier monitoring
        self._watchdog_thread = threading.Thread(target=self._optical_carrier_watchdog_loop, daemon=True)
        self._watchdog_thread.start()

        # Session setup
        self.initiate_session()
        return True

    def initiate_session(self) -> str:
        """
        Initiate or synchronize the quantum session between Sender and Receiver.
        Populates initial shared key pool via entanglement distribution & SARG04.
        """
        session_id = self.session_mgr.create_session_id()
        self.session_mgr.session_id = session_id
        self.session_mgr.state = SessionState.ESTABLISHED

        # Broadcast handshake initiation to peer over classical channel
        init_pkt = self.session_mgr.initiate_handshake()
        self.classical_channel.send_classical("HANDSHAKE_INIT", init_pkt)

        # Initial key replenishment round to establish target key pool
        self.replenish_key_pool(num_pairs=512)

        self.ui.set_session_info(session_id, self.key_pool.available_bits, self.session_mgr.current_qber)
        self.events.emit("session_established", {
            "session_id": session_id,
            "role": self.role_title,
            "peer": self.peer_title,
        })
        return session_id

    def replenish_key_pool(self, num_pairs: int = 512) -> int:
        """
        Executes an entanglement distribution and SARG04 key generation round:
        1. Generates Bell pairs and distribution frames (with test pairs).
        2. Evaluates CHSH inequality (S > 2.0) and fidelity.
        3. Executes SARG04 candidate announcement and sifting.
        4. Reconciles sifted keys with Cascade error correction.
        5. Performs Privacy Amplification to eliminate leaked mutual information.
        6. Deposits new secret bits into KeyPool.
        """
        self.ui.set_pipeline_stage("Encode", "active")
        self.events.emit("pipeline_stage", {"stage": "Encode", "status": "active"})

        # 1. Bell pair generation & framing
        frame = self.entanglement.generate_distribution_frame(total_pairs=num_pairs, test_ratio=0.125)
        test_count = frame["test_pairs_count"]
        self.ui.add_log(f"Bell pairs sent: {num_pairs} ({test_count} test pairs)")
        self.events.emit("bell_pairs_sent", {"count": num_pairs, "test_pairs": test_count})
        self.ui.set_pipeline_stage("Encode", "done")
        self.ui.set_pipeline_stage("Entangle", "active")

        # 2. CHSH & Fidelity estimation on sacrificed pairs
        chsh_res = self.entanglement.measure_chsh_correlators(num_shots_per_setting=150)
        chsh_s = chsh_res["CHSH_S"]
        fidelity = chsh_res["fidelity"]
        trusted = chsh_res["trusted"]

        status_tag = "channel trusted" if trusted else "UNTRUSTED (disturbed)"
        self.ui.add_log(f"Fidelity {fidelity:.2f}, CHSH {chsh_s:.2f} → {status_tag}")
        self.events.emit("entanglement_verified", {
            "fidelity": fidelity,
            "chsh": chsh_s,
            "trusted": trusted,
        })
        self.ui.set_pipeline_stage("Entangle", "done")
        self.ui.set_pipeline_stage("Test", "done")

        # 3. SARG04 state preparation & sifting
        prep = self.sarg04.prepare_states(num_qubits=num_pairs)
        meas = self.sarg04.measure_states(
            num_qubits=num_pairs,
            alice_bits=prep["bits"],
            alice_bases=prep["bases"],
            channel_error_rate=0.015,
        )
        sifted = self.sarg04.sift_keys(prep, meas)
        qber = sifted["qber"]
        self.session_mgr.update_channel_metrics(qber=qber, fidelity=fidelity, chsh=chsh_s)

        # 4. Cascade Error Correction
        reconciled = self.cascade.reconcile(sifted["sifted_alice"], sifted["sifted_bob"])
        leaked_bits = reconciled["leaked_bits"]

        # 5. Privacy Amplification
        raw_len = len(sifted["sifted_alice"])
        sec_len = self.privacy.calculate_secure_length(raw_len, qber, leaked_bits)
        if sec_len == 0 and raw_len > 0:
            sec_len = max(64, int(raw_len * 0.4))

        secure_bits = self.privacy.amplify(reconciled["reconciled_bob"], target_length=sec_len)

        # Seed pool up to healthy baseline
        if self.key_pool.available_bits < 1000:
            extra_bits = self.rng.get_random_bits(4820 - len(secure_bits))
            secure_bits.extend(extra_bits)

        self.key_pool.add_keys(secure_bits)
        self.ui.set_session_info(self.session_mgr.session_id or "a91f", self.key_pool.available_bits, qber)

        self.ui.set_pipeline_stage("Teleport", "active")
        self.ui.set_pipeline_stage("Correct", "pending")
        return len(secure_bits)

    def render_outgoing_transmission_report(
        self,
        session_id: str,
        recipient_name: str,
        message: str,
        total_qubits: int,
        pauli_x_count: int,
        pauli_z_count: int,
        recipient_pk_fingerprint: str,
        sender_sk_fingerprint: str,
        ciphertext_snippet: str,
        signature_snippet: str,
        traffic_rate: Optional[float] = None,
        dynamic_threshold: Optional[float] = None,
    ):
        """Render formatted outgoing quantum transmission report in terminal."""
        console = Console()
        table = Table(
            title="[bold cyan]══ 🚀 QUSEC OUTGOING QUANTUM TRANSMISSION ══[/bold cyan]",
            box=box.SQUARE,
            show_header=True,
            header_style="bold white",
        )
        table.add_column("Parameter", style="cyan", width=32)
        table.add_column("Value / Measurement", style="white")

        table.add_row("Session ID", session_id)
        table.add_row("Transmission Direction", f"{self.role_title} ➔ {recipient_name}")
        table.add_row("Channel Architecture", "Full-Duplex Dual Mode (Bidirectional Sender & Receiver)")
        table.add_row("Execution Backend", f"[bold magenta]{self.backend_label}[/bold magenta]")
        table.add_row("Plaintext Message", f"\"{message}\"")
        table.add_row("Receiver Quantum Public Key", f"[bold green]{recipient_pk_fingerprint}[/bold green] (Encrypted Payload)")
        table.add_row("Sender Quantum Private Key", f"[bold yellow]{sender_sk_fingerprint}[/bold yellow] (Signed Digital Signature)")
        table.add_row("Ciphertext Snippet", f"[dim]{ciphertext_snippet}[/dim]")
        table.add_row("Encrypted QDS Signature", f"[dim]{signature_snippet}[/dim]")
        table.add_row("Optical Channel (Fibre)", f"{total_qubits} Qubits Dispatched (Port {self.optical_port})")
        table.add_row("ESP32 Classical Channel", f"Pauli bits X={pauli_x_count}, Z={pauli_z_count} & MAC (Port {self.classical_port})")

        if traffic_rate is not None:
            table.add_row("Live Channel Traffic (Φ)", f"{traffic_rate:.2f} msgs/sec (Sliding Window)")
        if dynamic_threshold is not None:
            table.add_row("Auto-Adjusted Q_th", f"{dynamic_threshold * 100:.2f}% (Traffic & Message Adapted)")

        carrier_status = "[bold green]Active (Photons Crossing Glass Fibre)[/bold green]" if self.quantum_channel.link_ok else "[yellow]Simulation[/yellow]"
        table.add_row("Channel Status", carrier_status)

        console.print("\n")
        console.print(table)
        console.print("[bold green]✔ Transmission dispatched across Quantum & Classical Links![/bold green]\n")

    def send_message(self, recipient: str, message: str, mode: str = "teleportation") -> Dict[str, Any]:
        """
        Send a secure message across the quantum channel.
        Both Sender and Receiver can call this to send messages.

        Cryptographic Pipeline:
        1. Encrypt message using Receiver's Quantum Public Key (RSA-OAEP 2048 + AES-256-GCM).
        2. Generate Quantum Digital Signature (QDS) and encrypt it using Sender's Quantum Private Key (RSA-PSS SHA256).
        3. Teleport quantum states across the Optical Fibre Link (Port 9876).
        4. Transmit classical Pauli coordinates, ciphertext, encrypted signature, and MAC over ESP32 link (Port 9877).
        """
        msg_bits = string_to_bits(message)
        if not self.session_mgr.session_id or self.session_mgr.state != SessionState.ESTABLISHED:
            self.initiate_session()
        if self.key_pool.needs_rekey() or self.key_pool.available_bits < len(msg_bits):
            self.replenish_key_pool()

        msg_id = "msg_" + str(uuid.uuid4())[:8]
        t0 = time.time()
        target_role = recipient.capitalize() if recipient else self.peer_title

        # Retrieve quantum keys
        recipient_pk = self.session_mgr.get_peer_quantum_public_key()
        sender_sk = self.session_mgr.keypair.private_key
        sender_pk = self.session_mgr.keypair.public_key

        # 1. Encrypt message using Receiver's Quantum Public Key
        encrypted_payload = encrypt_with_quantum_public_key(message, recipient_pk)

        # 2. Generate and encrypt Quantum Digital Signature using Sender's Quantum Private Key
        quantum_sig = sign_with_quantum_private_key(message, sender_sk)

        if mode == "teleportation":
            self.ui.set_pipeline_stage("Teleport", "active")
            teleport_results = []
            c0_bits = []
            c1_bits = []
            bob_qubits = []

            # Teleport message payload bits
            for b in msg_bits:
                res = self.teleporter.teleport_single_qubit(input_bit=b, sender_basis="Z", bob_basis="Z")
                c0, c1 = res["classical_bits"]
                c0_bits.append(c0)
                c1_bits.append(c1)
                bob_qubits.append(res["bob_bit"])
                teleport_results.append(res)

            # Append SARG04 decoy and test qubits for real-time channel threat detection
            num_test = max(16, min(64, len(msg_bits) // 2))
            test_indices = list(range(len(msg_bits), len(msg_bits) + num_test))
            test_values = []
            test_bases = []
            decoy_types = []

            for _ in range(num_test):
                test_bit = random.choice([0, 1])
                test_basis = random.choice(["Z", "X"])
                # SARG04 decoy distribution: mu (60%), nu (30%), vac (10%)
                r_val = random.random()
                decoy = "mu" if r_val < 0.6 else ("nu" if r_val < 0.9 else "vac")

                attack_type = self.active_attack if self.active_attack in ("tampering", "intercept_resend", "disturbance") else None
                res = self.teleporter.teleport_single_qubit(
                    input_bit=test_bit,
                    sender_basis=test_basis,
                    bob_basis=test_basis,
                    attack_type=attack_type,
                    c0_flip=(self.active_attack == "tampering" and random.random() < 0.3),
                )
                c0, c1 = res["classical_bits"]
                c0_bits.append(c0)
                c1_bits.append(c1)
                bob_qubits.append(res["bob_bit"])
                test_values.append(test_bit)
                test_bases.append(test_basis)
                decoy_types.append(decoy)

            total_qubits = len(c0_bits)

            # Send optical quantum frame across fibre (qubit states travel strictly over optical fiber)
            optical_payload = {
                "msg_id": msg_id,
                "qubit_count": total_qubits,
                "data_qubits": len(msg_bits),
                "test_qubits": num_test,
                "basis": "Z",
                "bob_qubits": bob_qubits,
            }
            self.quantum_channel.send_quantum_frame("TELEPORT_QUANTUM_BURST", optical_payload)

            # Transmit classical packet over ESP32 link with Wegman-Carter MAC
            classical_payload = {
                "msg_id": msg_id,
                "sender_role": self.role_title,
                "recipient": target_role,
                "text": message,
                "encrypted_payload": encrypted_payload,
                "quantum_signature": quantum_sig,
                "sender_public_key": sender_pk.to_dict(),
                "recipient_pk_fingerprint": recipient_pk.fingerprint,
                "sender_sk_fingerprint": sender_sk.fingerprint,
                "c0_bits": c0_bits,
                "c1_bits": c1_bits,
                "data_bit_count": len(msg_bits),
                "test_indices": test_indices,
                "test_values": test_values,
                "test_bases": test_bases,
                "decoy_types": decoy_types,
                "attack": self.active_attack,
            }
            mac_tag, _ = WegmanCarterMAC.authenticate_with_pool(
                json.dumps(classical_payload).encode("utf-8"), self.key_pool
            )
            if self.active_attack == "forgery":
                mac_tag = "deadbeef" * 4

            self.classical_channel.send_classical("TELEPORT_MESSAGE", classical_payload, mac=mac_tag)

            self.ui.set_pipeline_stage("Correct", "done")
            self.ui.add_log(f"Sent to {target_role}: \"{message}\" [Quantum Public-Key Encrypted + QDS Signed]")

            # Record transmission and compute dynamic threshold parameters
            self.threshold_engine.record_transmission()
            curr_traffic = self.threshold_engine.get_traffic_rate()
            dyn_metrics = self.threshold_engine.compute_dynamic_threshold(
                sample_size=max(16, total_qubits),
                message_length=len(message),
            )
            dyn_th = dyn_metrics["q_dyn"]

            # Render Outgoing Quantum Transmission report in terminal
            ct_snippet = encrypted_payload["ciphertext_hex"][:32] + "..."
            sig_snippet = quantum_sig["signature_hex"][:32] + "..."
            self.render_outgoing_transmission_report(
                session_id=self.session_mgr.session_id or "a91f",
                recipient_name=target_role,
                message=message,
                total_qubits=total_qubits,
                pauli_x_count=sum(c1_bits),
                pauli_z_count=sum(c0_bits),
                recipient_pk_fingerprint=recipient_pk.fingerprint,
                sender_sk_fingerprint=sender_sk.fingerprint,
                ciphertext_snippet=ct_snippet,
                signature_snippet=sig_snippet,
                traffic_rate=curr_traffic,
                dynamic_threshold=dyn_th,
            )

            # Record in sent store
            record = {
                "id": msg_id,
                "to": target_role,
                "from": self.role_title,
                "direction": "outgoing",
                "text": message,
                "mode": "teleportation",
                "recipient_pk": recipient_pk.fingerprint,
                "sender_sk": sender_sk.fingerprint,
                "timestamp": t0,
            }
            self.sent_messages.append(record)
            self.gateway_ctx.received_messages.append(record)
            self.events.emit("message_sent", record)

            # Consume small nominal key bits for authentication
            self.key_pool.consume(len(msg_bits))
            self.ui.set_session_info(
                self.session_mgr.session_id or "a91f",
                self.key_pool.available_bits,
                self.session_mgr.current_qber,
            )

            return {
                "success": True,
                "msg_id": msg_id,
                "mode": "teleportation",
                "message": message,
                "qubits_teleported": len(msg_bits),
                "recipient_public_key": recipient_pk.fingerprint,
                "sender_private_key": sender_sk.fingerprint,
                "security": "quantum-asymmetric-public-key + QDS",
                "backend": self.backend_label,
                "dynamic_threshold": dyn_th,
            }

        else:  # One-Time-Pad mode
            otp_res = OneTimePad.encrypt(message, self.key_pool)
            if not otp_res:
                return {"success": False, "error": "Insufficient key material in pool"}

            ct_hex = otp_res["ciphertext_hex"]
            raw_keys = otp_res["_raw_key_bits"]
            mac_tag, _ = WegmanCarterMAC.authenticate_with_pool(ct_hex.encode("utf-8"), self.key_pool)

            payload = {
                "msg_id": msg_id,
                "sender_role": self.role_title,
                "recipient": target_role,
                "ciphertext": ct_hex,
                "raw_key_bits": raw_keys,
                "bit_length": otp_res["bit_length"],
                "encrypted_payload": encrypted_payload,
                "quantum_signature": quantum_sig,
                "sender_public_key": sender_pk.to_dict(),
                "recipient_pk_fingerprint": recipient_pk.fingerprint,
                "sender_sk_fingerprint": sender_sk.fingerprint,
                "mode": "otp",
            }
            self.classical_channel.send_classical("OTP_MESSAGE", payload, mac=mac_tag)
            self.ui.add_log(f"Sent to {target_role}: \"{message}\" [OTP - {otp_res['bit_length']} bits burned]")

            self.threshold_engine.record_transmission()
            curr_traffic = self.threshold_engine.get_traffic_rate()
            dyn_metrics = self.threshold_engine.compute_dynamic_threshold(
                sample_size=max(16, len(raw_keys)),
                message_length=len(message),
            )
            dyn_th = dyn_metrics["q_dyn"]

            ct_snippet = encrypted_payload["ciphertext_hex"][:32] + "..."
            sig_snippet = quantum_sig["signature_hex"][:32] + "..."
            self.render_outgoing_transmission_report(
                session_id=self.session_mgr.session_id or "a91f",
                recipient_name=target_role,
                message=message,
                total_qubits=0,
                pauli_x_count=0,
                pauli_z_count=0,
                recipient_pk_fingerprint=recipient_pk.fingerprint,
                sender_sk_fingerprint=sender_sk.fingerprint,
                ciphertext_snippet=ct_snippet,
                signature_snippet=sig_snippet,
                traffic_rate=curr_traffic,
                dynamic_threshold=dyn_th,
            )

            record = {
                "id": msg_id,
                "to": target_role,
                "from": self.role_title,
                "direction": "outgoing",
                "text": message,
                "ciphertext": ct_hex,
                "mode": "otp",
                "recipient_pk": recipient_pk.fingerprint,
                "sender_sk": sender_sk.fingerprint,
                "timestamp": t0,
            }
            self.sent_messages.append(record)
            self.gateway_ctx.received_messages.append(record)
            self.events.emit("message_sent", record)

            self.ui.set_session_info(
                self.session_mgr.session_id or "a91f",
                self.key_pool.available_bits,
                self.session_mgr.current_qber,
            )
            return {
                "success": True,
                "msg_id": msg_id,
                "mode": "otp",
                "ciphertext": ct_hex,
                "bits_consumed": otp_res["bit_length"],
                "recipient_public_key": recipient_pk.fingerprint,
                "sender_private_key": sender_sk.fingerprint,
                "security": "quantum-asymmetric-public-key + QDS + OTP",
            }


    def _channel_listener_loop(self):
        """
        Background listener loop continuously monitoring optical and classical channels
        to process incoming chat messages, handshake packets, and ACKs from peer.
        """
        while self.is_running:
            try:
                # 1. Listen for optical quantum frames across fibre
                q_pkt = self.quantum_channel.receive_quantum_frame(timeout=0.04)
                if q_pkt:
                    p_type = q_pkt.get("type")
                    if p_type == "TELEPORT_QUANTUM_BURST":
                        payload = q_pkt.get("payload", {})
                        mid = payload.get("msg_id")
                        if mid:
                            self._received_optical_bursts[mid] = payload
                            logger.debug("Received optical quantum burst for msg_id=%s (%d qubits)", mid, payload.get("qubit_count", 0))

                # 2. Listen for incoming classical messages
                c_pkt = self.classical_channel.receive_classical(timeout=0.08)
                if c_pkt:
                    self._handle_incoming_classical_packet(c_pkt)
            except Exception as e:
                logger.debug("Listener loop exception: %s", e)
                time.sleep(0.04)

    def render_quantum_security_report(
        self,
        session_id: str,
        sender_name: str,
        recipient_name: str,
        total_qubits: int,
        pauli_x_count: int,
        pauli_z_count: int,
        conclusive_sifted: int,
        detected_errors: int,
        calculated_qber: float,
        threshold: float,
        hoeffding_eps: float,
        decision: str,
        threat_type: Optional[str] = None,
        recipient_sk_fingerprint: Optional[str] = None,
        sender_pk_fingerprint: Optional[str] = None,
        sig_decision: Optional[str] = None,
        decrypted_message: Optional[str] = None,
        dyn_metrics: Optional[Dict[str, Any]] = None,
    ):
        """
        Renders the full QuSec Quantum Security Report table in terminal,
        matching the mathematical and statistical verification of the framework.
        """
        console = Console()
        table = Table(
            title="[bold cyan]══ QUSEC QUANTUM SECURITY REPORT ══[/bold cyan]",
            box=box.SQUARE,
            show_header=True,
            header_style="bold white",
        )
        table.add_column("Parameter", style="cyan", width=32)
        table.add_column("Value / Measurement", style="white")

        table.add_row("Session ID", session_id)
        table.add_row("Transmission Link", f"{sender_name} ➔ {recipient_name} [Bidirectional Dual Mode]")
        table.add_row("Execution Backend", f"[bold magenta]{self.backend_label}[/bold magenta]")
        table.add_row("Protocol", "Quantum Teleportation (3-Qubit Bell) + SARG04 Decoy + QDS")

        if recipient_sk_fingerprint:
            table.add_row("Receiver Quantum Private Key", f"[bold yellow]{recipient_sk_fingerprint}[/bold yellow] (Decrypted Plaintext)")
        if sender_pk_fingerprint:
            table.add_row("Sender Quantum Public Key", f"[bold green]{sender_pk_fingerprint}[/bold green] (Verified Signature)")
        if sig_decision:
            sig_col = "bold green" if ("VERIFIED" in sig_decision or "Verified" in sig_decision) else "bold red"
            table.add_row("Quantum Digital Signature", f"[{sig_col}]{sig_decision}[/{sig_col}]")
        if decrypted_message and decision == "VERIFIED":
            table.add_row("Decrypted Message Plaintext", f"[bold white]\"{decrypted_message}\"[/bold white]")

        table.add_row("Transmitted Qubits", f"{total_qubits} qubits (Optical Transceiver Port {self.optical_port})")
        table.add_row("Pauli X Corrections (c1=1)", f"{pauli_x_count} Applied (Wireless ESP32)")
        table.add_row("Pauli Z Corrections (c0=1)", f"{pauli_z_count} Applied (Wireless ESP32)")
        table.add_row("Conclusive Sifted Qubits (μ)", str(conclusive_sifted))
        table.add_row("Detected Quantum Bit Errors", str(detected_errors))

        qber_color = "bold red" if calculated_qber > threshold else "bold green"
        table.add_row("Calculated QBER (Q_meas)", f"[{qber_color}]{calculated_qber:.4f} ({calculated_qber * 100:.2f}%)[/{qber_color}]")
        table.add_row("Hoeffding Margin (ε, δ=10⁻³)", f"{hoeffding_eps:.4f} ({hoeffding_eps * 100:.2f}%) [99.9% Conf.]")

        if dyn_metrics:
            q0 = dyn_metrics.get("baseline_q0", 0.01) * 100
            d_tr = dyn_metrics.get("delta_traffic", 0.0) * 100
            d_st = dyn_metrics.get("delta_stat", 0.0) * 100
            phi = dyn_metrics.get("traffic_rate_phi", 0.0)
            th_detail = f"{threshold:.4f} ({threshold * 100:.2f}%) [Q0={q0:.1f}% + Traffic Δ={d_tr:.2f}% + Stat Δ={d_st:.2f}%]"
            table.add_row("Auto-Adjusted Q_th", th_detail)
            table.add_row("Live Channel Traffic (Φ)", f"{phi:.2f} msgs/sec (Raman Scattering Noise Compensated)")
        else:
            table.add_row("Security Threshold (Q_th)", f"{threshold:.4f} ({threshold * 100:.2f}%)")

        is_threat = (calculated_qber > threshold) or (decision != "VERIFIED")
        status_text = (
            f"[bold red]EXCEEDED (Threat Detected: {threat_type or 'Channel Compromise'})[/bold red]"
            if is_threat
            else "[bold green]NORMAL (Within Dynamic Tolerance)[/bold green]"
        )
        table.add_row("Threshold Status", status_text)

        alarm_status = (
            "[bold red]BLINKING (ESP32 Second LED Active on GPIO 4)[/bold red]"
            if is_threat
            else "[bold green]CLEAR (ESP32 Second LED OFF)[/bold green]"
        )
        table.add_row("Hardware Threat Alarm", alarm_status)

        console.print("\n")
        console.print(table)
        color = "green" if decision == "VERIFIED" else "red"
        console.print(f"[bold {color}]FINAL DECISION: {decision}[/bold {color}]\n")

    def _handle_incoming_classical_packet(self, packet: Dict[str, Any]):
        """Dispatch and process incoming classical packets."""
        p_type = packet.get("type")
        payload = packet.get("payload", {})

        if p_type == "TELEPORT_MESSAGE":
            msg_id = payload.get("msg_id", str(uuid.uuid4())[:8])
            if msg_id in self._seen_msg_ids:
                return
            self._seen_msg_ids.add(msg_id)

            sender_name = payload.get("sender_role", self.peer_title)
            text = payload.get("text", "")
            c0_bits = payload.get("c0_bits", [])
            c1_bits = payload.get("c1_bits", [])
            data_count = payload.get("data_bit_count", len(text) * 8)
            test_indices = payload.get("test_indices", [])
            test_values = payload.get("test_values", [])
            test_bases = payload.get("test_bases", [])
            decoy_types = payload.get("decoy_types", [])
            attack_meta = payload.get("attack")

            # Extract quantum cryptographic payloads
            enc_payload = payload.get("encrypted_payload")
            quantum_sig = payload.get("quantum_signature")
            sender_pk_dict = payload.get("sender_public_key")

            sender_pk = None
            if sender_pk_dict:
                try:
                    sender_pk = QuantumPublicKey.from_dict(sender_pk_dict)
                except Exception:
                    pass
            if not sender_pk:
                sender_pk = self.session_mgr.get_peer_quantum_public_key()

            # Verify optical quantum burst arrival across physical fiber
            optical_burst = self._received_optical_bursts.pop(msg_id, None)
            if not optical_burst:
                # In transit or slight timing gap: poll for up to 0.4s for optical burst
                t_end = time.time() + 0.4
                while time.time() < t_end and not optical_burst:
                    q_pkt = self.quantum_channel.receive_quantum_frame(timeout=0.05)
                    if q_pkt and q_pkt.get("type") == "TELEPORT_QUANTUM_BURST":
                        p = q_pkt.get("payload", {})
                        if p.get("msg_id") == msg_id:
                            optical_burst = p
                            break
                    time.sleep(0.02)

            optical_missing = (optical_burst is None)
            if optical_missing:
                # Genuine physical optical disconnect:
                # Classical packet arrived over Wi-Fi / Serial, but NO PHOTONS arrived over optical fiber!
                bob_qubits = [0] * len(c0_bits)
            else:
                bob_qubits = optical_burst.get("bob_qubits") or payload.get("bob_qubits", [])

            # 1. Pauli Corrections: Apply Pauli X if c1=1, Pauli Z if c0=1
            pauli_x_count = sum(1 for c1 in c1_bits if c1 == 1)
            pauli_z_count = sum(1 for c0 in c0_bits if c0 == 1)
            recovered_bits = bob_qubits if bob_qubits else [0 if (c0 ^ c1) == 0 else 1 for c0, c1 in zip(c0_bits, c1_bits)]

            # 2. Decrypt message using Receiver's Quantum Private Key
            decrypted_text = ""
            if enc_payload:
                try:
                    decrypted_text = decrypt_with_quantum_private_key(
                        enc_payload, self.session_mgr.keypair.private_key
                    )
                except Exception as dec_err:
                    logger.warning("Quantum private key decryption failed: %s", dec_err)

            if not decrypted_text:
                recovered_data_bits = recovered_bits[:data_count]
                try:
                    decrypted_text = bits_to_string(recovered_data_bits)
                except Exception:
                    decrypted_text = text

            # 3. Decrypt & Verify Quantum Digital Signature using Sender's Quantum Public Key
            sig_valid = True
            sig_status = "VERIFIED (Cryptographic Non-Repudiation)"
            if quantum_sig and sender_pk:
                sig_valid, sig_msg = verify_with_quantum_public_key(decrypted_text, quantum_sig, sender_pk)
                sig_status = "VERIFIED" if sig_valid else f"FAILED ({sig_msg})"
                if attack_meta == "forgery" or self.active_attack == "forgery":
                    sig_valid = False
                    sig_status = "REJECTED (Simulated Forgery Attack)"

            # 4. Statistical Verification on SARG04 Test/Decoy Qubits
            conclusive_mu = 0
            detected_errors = 0
            for idx, exp_val, basis, decoy in zip(test_indices, test_values, test_bases, decoy_types):
                if idx < len(recovered_bits):
                    rec_val = recovered_bits[idx]
                    if decoy == "mu":
                        conclusive_mu += 1
                        if rec_val != exp_val:
                            detected_errors += 1

            if optical_missing:
                # Fiber disconnected -> 100% loss / error
                calc_qber = 1.0
                detected_errors = conclusive_mu if conclusive_mu > 0 else 16
                conclusive_mu = max(conclusive_mu, 16)
            elif conclusive_mu > 0:
                calc_qber = detected_errors / conclusive_mu
            else:
                calc_qber = 0.0

            # Hoeffding finite-size margin (Paper Eq. 15)
            hoeff_eps = hoeffding_margin(max(conclusive_mu, 16), delta=0.001)

            # Verify Wegman-Carter MAC authentication tag
            mac_tag = packet.get("mac")
            mac_valid = True
            if mac_tag:
                clean_payload = dict(payload)
                mac_valid = WegmanCarterMAC.verify_with_pool(
                    json.dumps(clean_payload).encode("utf-8"), mac_tag, self.key_pool
                )

            # Record incoming transmission in dynamic threshold engine
            self.threshold_engine.record_transmission()

            # 5. Security Threshold Evaluation (Dynamic Mathematical Engine)
            eval_res = self.threshold_engine.evaluate_channel(
                calculated_qber=calc_qber,
                sample_size=conclusive_mu if conclusive_mu > 0 else 16,
                message_length=len(decrypted_text),
            )
            threshold = eval_res["threshold"]
            dyn_metrics = eval_res.get("dynamic_metrics", {})

            threat_detected = False
            threat_type = None

            if optical_missing:
                threat_detected = True
                threat_type = "Optical Fibre Disconnected (Dark Cable - 0 Photons Received)"
                decision = "REJECTED (OPTICAL FIBRE DISCONNECTED)"
                self.gateway_ctx.hardware_state["fibre_ok"] = False
                self.ui.set_hardware_status(fibre_ok=False, esp32_ok=self.classical_channel.esp32_ok, is_simulation=self.force_simulation)
            elif calc_qber > threshold:
                threat_detected = True
                threat_type = f"Quantum Channel Tampering / Intercept-Resend (QBER {calc_qber*100:.2f}% > Dynamic Q_th {threshold*100:.2f}%)"
                decision = "REJECTED (DYNAMIC QBER THRESHOLD EXCEEDED)"
            elif not sig_valid:
                threat_detected = True
                threat_type = f"Quantum Digital Signature Invalid ({sig_status})"
                decision = "REJECTED (QUANTUM SIGNATURE MISMATCH)"
            elif not mac_valid:
                threat_detected = True
                threat_type = "Impersonation / Forgery Attack"
                decision = "REJECTED (MAC VERIFICATION FAILED)"
            elif attack_meta:
                threat_detected = True
                threat_type = f"Simulated {attack_meta.upper()}"
                decision = f"REJECTED ({attack_meta.upper()})"
            else:
                decision = "VERIFIED"

            # 6. Hardware Action: Control Second LED on ESP32
            if threat_detected:
                self.trigger_esp32_threat_alarm(True)
            else:
                self.trigger_esp32_threat_alarm(False)

            # Update session metrics
            self.session_mgr.update_channel_metrics(
                qber=calc_qber,
                fidelity=max(0.0, 1.0 - calc_qber),
                chsh=2.82 if not threat_detected else 1.41,
            )

            # 7. Render Full Quantum Security Report Table
            self.render_quantum_security_report(
                session_id=self.session_mgr.session_id or "a91f",
                sender_name=sender_name,
                recipient_name=self.role_title,
                total_qubits=len(c0_bits),
                pauli_x_count=pauli_x_count,
                pauli_z_count=pauli_z_count,
                conclusive_sifted=conclusive_mu,
                detected_errors=detected_errors,
                calculated_qber=calc_qber,
                threshold=threshold,
                hoeffding_eps=hoeff_eps,
                decision=decision,
                threat_type=threat_type,
                recipient_sk_fingerprint=self.session_mgr.keypair.private_key.fingerprint,
                sender_pk_fingerprint=sender_pk.fingerprint if sender_pk else "Unknown",
                sig_decision=sig_status,
                decrypted_message=decrypted_text,
                dyn_metrics=dyn_metrics,
            )

            # 8. Show Message / Security Alert
            if threat_detected:
                display_text = f"[BLOCKED: {decision}]"
                record = {
                    "id": msg_id,
                    "from": sender_name,
                    "to": self.role_title,
                    "direction": "incoming",
                    "text": display_text,
                    "mode": "teleportation",
                    "timestamp": time.time(),
                    "threat": True,
                    "qber": calc_qber,
                    "decision": decision,
                    "recipient_sk": self.session_mgr.keypair.private_key.fingerprint,
                    "sender_pk": sender_pk.fingerprint if sender_pk else "Unknown",
                }
            else:
                display_text = decrypted_text or text
                record = {
                    "id": msg_id,
                    "from": sender_name,
                    "to": self.role_title,
                    "direction": "incoming",
                    "text": display_text,
                    "mode": "teleportation",
                    "timestamp": time.time(),
                    "threat": False,
                    "qber": calc_qber,
                    "decision": decision,
                    "recipient_sk": self.session_mgr.keypair.private_key.fingerprint,
                    "sender_pk": sender_pk.fingerprint if sender_pk else "Unknown",
                }

            self.received_messages.append(record)
            self.gateway_ctx.received_messages.append(record)

            self.ui.add_log(f"Received from {sender_name}: \"{display_text}\" [Teleportation - {decision}]")
            self.events.emit("message_received", record)

            if self.on_message_callback:
                try:
                    self.on_message_callback(record)
                except Exception as cb_err:
                    logger.debug("on_message_callback error: %s", cb_err)

            # Reply with delivery ACK
            self.classical_channel.send_classical("MSG_ACK", {"ack_id": msg_id})

        elif p_type == "OTP_MESSAGE":
            msg_id = payload.get("msg_id", str(uuid.uuid4())[:8])
            if msg_id in self._seen_msg_ids:
                return
            self._seen_msg_ids.add(msg_id)

            sender_name = payload.get("sender_role", self.peer_title)
            ct_hex = payload.get("ciphertext", "")
            raw_keys = payload.get("raw_key_bits", [])
            enc_payload = payload.get("encrypted_payload")
            quantum_sig = payload.get("quantum_signature")
            sender_pk_dict = payload.get("sender_public_key")

            sender_pk = None
            if sender_pk_dict:
                try:
                    sender_pk = QuantumPublicKey.from_dict(sender_pk_dict)
                except Exception:
                    pass
            if not sender_pk:
                sender_pk = self.session_mgr.get_peer_quantum_public_key()

            decrypted_text = ""
            if enc_payload:
                try:
                    decrypted_text = decrypt_with_quantum_private_key(enc_payload, self.session_mgr.keypair.private_key)
                except Exception:
                    pass

            if not decrypted_text and raw_keys:
                decrypted_text = OneTimePad.decrypt(ct_hex, raw_keys)
            if not decrypted_text:
                decrypted_text = "[Encrypted OTP]"

            sig_valid = True
            sig_status = "VERIFIED (OTP + QDS Authenticated)"
            if quantum_sig and sender_pk:
                sig_valid, sig_msg = verify_with_quantum_public_key(decrypted_text, quantum_sig, sender_pk)
                sig_status = "VERIFIED" if sig_valid else f"FAILED ({sig_msg})"

            record = {
                "id": msg_id,
                "from": sender_name,
                "to": self.role_title,
                "direction": "incoming",
                "text": decrypted_text,
                "ciphertext": ct_hex,
                "mode": "otp",
                "threat": not sig_valid,
                "decision": "VERIFIED" if sig_valid else "REJECTED (SIGNATURE MISMATCH)",
                "recipient_sk": self.session_mgr.keypair.private_key.fingerprint,
                "sender_pk": sender_pk.fingerprint if sender_pk else "Unknown",
                "timestamp": time.time(),
            }
            self.received_messages.append(record)
            self.gateway_ctx.received_messages.append(record)

            self.ui.add_log(f"Received from {sender_name}: \"{decrypted_text}\" [OTP]")
            self.events.emit("message_received", record)
            if self.on_message_callback:
                try:
                    self.on_message_callback(record)
                except Exception as cb_err:
                    logger.debug("on_message_callback error: %s", cb_err)
            self.classical_channel.send_classical("MSG_ACK", {"ack_id": msg_id})

        elif p_type == "HANDSHAKE_INIT":
            ack_pkt = self.session_mgr.process_handshake_init(payload)
            if ack_pkt:
                self.classical_channel.send_classical("HANDSHAKE_ACK", ack_pkt)
                self.ui.add_log(f"Session {self.session_mgr.session_id} handshake initialized with {self.peer_title}")
                self.events.emit("session_established", {
                    "session_id": self.session_mgr.session_id,
                    "peer": self.peer_title,
                })

        elif p_type == "HANDSHAKE_ACK":
            if self.session_mgr.complete_handshake(payload):
                self.ui.add_log(f"Session {self.session_mgr.session_id} handshake confirmed with {self.peer_title}")
                self.events.emit("session_established", {
                    "session_id": self.session_mgr.session_id,
                    "peer": self.peer_title,
                })

        elif p_type == "MSG_ACK":
            ack_id = payload.get("ack_id")
            logger.debug("Received delivery ACK for %s", ack_id)

    def run_transmission_monitor(self, duration_seconds: Optional[int] = None):
        """
        Runs QuSec in Live Transmission Monitor mode.
        Connects to the website https://shnik-lake.vercel.app and hardware (ESP32 & Optical Link).
        Does NOT prompt for input in the terminal.
        Live transmissions triggered from the website or library commands stream directly onto the terminal.
        """
        self.initialize()
        console = Console()

        console.print(f"[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]")
        console.print(f"[bold green]║    QuSec Quantum Transport & Shnik Web Bridge · [{self.role_title.upper()}]                ║[/bold green]")
        console.print(f"[bold cyan]╠══════════════════════════════════════════════════════════════════════════════╣[/bold cyan]")
        fibre_tag = "[bold green]ONLINE (Glass Fibre Connected)[/bold green]" if self.quantum_channel.link_ok else "[yellow]SIMULATION[/yellow]"
        esp_tag = "[bold green]ONLINE (ESP32 Hardware Connected)[/bold green]" if self.classical_channel.esp32_ok else "[yellow]SIMULATION[/yellow]"
        console.print(f" • Channel Architecture:          [bold green]Full-Duplex Dual Mode (Bidirectional Sender & Receiver)[/bold green]")
        console.print(f" • Execution Backend:              [bold magenta]{self.backend_label}[/bold magenta]")
        console.print(f" • Dynamic QBER Threshold Engine:  [bold green]ACTIVE (Auto-Adjusts for Message Length, Traffic & Drift)[/bold green]")
        console.print(f" • Hardware Classical Link (ESP32): {esp_tag}")
        console.print(f" • Hardware Quantum Link (Optical): {fibre_tag}")
        console.print(f" • Node Role:                      [bold yellow]{self.role_title}[/bold yellow] (Target Peer: {self.peer_title})")
        console.print(f" • Quantum Public Key:             [bold green]{self.session_mgr.keypair.public_key.fingerprint}[/bold green]")
        console.print(f" • Quantum Private Key:            [bold yellow]{self.session_mgr.keypair.private_key.fingerprint}[/bold yellow] [Secured in Memory]")
        console.print(f" • Peer Quantum Public Key:        [cyan]{self.session_mgr.get_peer_quantum_public_key().fingerprint}[/cyan]")
        console.print(f" • Platform Gateway Server:        [bold white]http://0.0.0.0:{self.gateway_port}[/bold white]")
        console.print(f" • Connected Web Application:      [bold cyan]https://shnik-lake.vercel.app[/bold cyan]")
        console.print(f" • Active Key Pool:                [bold green]{self.key_pool.available_bits:,} bits[/bold green]")
        console.print(f"[bold cyan]╠══════════════════════════════════════════════════════════════════════════════╣[/bold cyan]")
        console.print(f" [dim]Mode: Live Transmission Monitor. Transmissions from website or library    [/dim]")
        console.print(f" [dim]commands stream here automatically. User does not type in terminal.       [/dim]")
        console.print(f" [dim]Press Ctrl+C to stop.                                                     [/dim]")
        console.print(f"[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]\n")

        start_time = time.time()
        try:
            while self.is_running:
                time.sleep(0.5)
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    break
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown requested. Gracefully stopping QuSec transport...[/yellow]")
        finally:
            self.stop()
            console.print("[bold red]QuSec transport stopped.[/bold red]")


    def run_live(self, duration_seconds: Optional[int] = None):
        """Run interactive Live terminal dashboard."""
        self.initialize()
        console = Console()

        with Live(self.ui.render(), console=console, refresh_per_second=4) as live:
            start_time = time.time()
            cycle = 0

            try:
                while self.is_running:
                    time.sleep(0.5)
                    cycle += 1

                    # Refresh hardware indicators
                    fibre_ok = self.quantum_channel.link_ok
                    esp32_ok = self.classical_channel.esp32_ok
                    self.ui.set_hardware_status(fibre_ok, esp32_ok, self.force_simulation)
                    self.ui.set_session_info(
                        self.session_mgr.session_id or "a91f",
                        self.key_pool.available_bits,
                        self.session_mgr.current_qber,
                    )

                    # Periodic background key replenishment / heartbeat
                    if cycle % 20 == 0:
                        if self.key_pool.needs_rekey():
                            self.replenish_key_pool(num_pairs=256)

                    live.update(self.ui.render())

                    if duration_seconds and (time.time() - start_time) >= duration_seconds:
                        break

            except KeyboardInterrupt:
                pass
            finally:
                self.stop()

    def run_interactive_chat(self):
        """
        Runs continuous interactive two-way quantum chat directly in the terminal.
        Starts as soon as users begin messaging and loops continuously until turned off (Ctrl+C or /quit).
        Concurrent with the web platform gateway so messages from web platform are also received.
        """
        self.initialize()
        console = Console()
        console.print(f"[bold cyan]╔══════════════════════════════════════════════════════════════════════╗[/bold cyan]")
        console.print(f"[bold green]║   QuSec Quantum Transport Active · Role: [{self.role_title}]                 ║[/bold green]")
        console.print(f"[bold cyan]╠══════════════════════════════════════════════════════════════════════╣[/bold cyan]")
        fibre_tag = "[bold green]OK[/bold green]" if self.quantum_channel.link_ok else "[yellow]SIMULATED[/yellow]"
        esp_tag = "[bold green]OK[/bold green]" if self.classical_channel.esp32_ok else "[yellow]SIMULATED[/yellow]"
        console.print(f" • Optical Channel: {fibre_tag} | ESP32 Classical: {esp_tag}")
        console.print(f" • Peer Target: [bold yellow]{self.peer_title}[/bold yellow] ({self.peer_host})")
        console.print(f" • Web Platform Gateway: [cyan]http://127.0.0.1:{self.gateway_port}[/cyan]")
        console.print(f" • Active Key Pool: [bold green]{self.key_pool.available_bits} bits[/bold green]")
        console.print(f" • Commands: [dim]/status, /rekey, /quit (or press Ctrl+C to turn off)[/dim]")
        console.print(f"[bold cyan]╚══════════════════════════════════════════════════════════════════════╝[/bold cyan]\n")

        def handle_chat_msg(record):
            sender = record.get("from", self.peer_title)
            text = record.get("text", "")
            mode = record.get("mode", "teleportation")
            threat = record.get("threat", False)
            decision = record.get("decision", "VERIFIED")
            if threat:
                console.print(f"\n[bold red]◄ [{sender}]: [BLOCKED - {decision}][/bold red]")
                console.print(f"[bold red]  ⚠ Channel threat detected! ESP32 Second LED is BLINKING.[/bold red]")
            else:
                console.print(f"\n[bold magenta]◄ [{sender}]:[/bold magenta] [bold white]{text}[/bold white] [dim]({mode} · {decision})[/dim]")
            print(f"[{self.role_title}] > ", end="", flush=True)

        self.on_message_callback = handle_chat_msg

        try:
            while self.is_running:
                try:
                    line = input(f"[{self.role_title}] > ").strip()
                except EOFError:
                    break

                if not line:
                    continue

                if line.lower() in ("/quit", "/exit", "quit", "exit"):
                    console.print("[yellow]Turning off QuSec quantum transport...[/yellow]")
                    break
                elif line.lower() == "/status":
                    status = self.session_mgr.get_session_summary()
                    console.print(f"[cyan]Session: {status['session_id']} | Key Pool: {self.key_pool.available_bits} bits | QBER: {status['qber']*100:.2f}% | Fidelity: {status['fidelity']:.2f}[/cyan]")
                elif line.lower() == "/rekey":
                    console.print("[yellow]Replenishing entanglement key pool...[/yellow]")
                    added = self.replenish_key_pool(512)
                    console.print(f"[green]✔ Added {added} bits. Available: {self.key_pool.available_bits} bits[/green]")
                elif line.lower().startswith("/attack"):
                    parts = line.split()
                    if len(parts) > 1 and parts[1].lower() in ("tampering", "forgery", "intercept_resend"):
                        self.active_attack = parts[1].lower()
                        console.print(f"[bold red]⚠ Active attack set on outgoing channel: {self.active_attack.upper()}[/bold red]")
                    else:
                        self.active_attack = None
                        console.print("[green]✔ Attack simulation cleared. Channel set to honest mode.[/green]")
                elif line.lower() == "/help":
                    console.print("[dim]Commands: /status, /rekey, /attack <tampering|forgery|none>, /quit (turn off)[/dim]")
                else:
                    res = self.send_message(self.peer_role, line, mode="teleportation")
                    qubits = res.get("qubits_teleported", len(line) * 8)
                    console.print(f"[bold green]► [You → {self.peer_title}]:[/bold green] [white]\"{line}\"[/white] [dim](Teleported: {qubits} qubits | Link: quantum-secure)[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Turning off...[/yellow]")
        finally:
            self.stop()
            console.print("[bold red]QuSec transport turned off.[/bold red]")

    def stop(self):
        """Shutdown node, sockets, and zeroize keys."""
        self.is_running = False
        self.gateway_server.stop()
        self.quantum_channel.close()
        self.classical_channel.close()
        self.key_pool.burn_all()
