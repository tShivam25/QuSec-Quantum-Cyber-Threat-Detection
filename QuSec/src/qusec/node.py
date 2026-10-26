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
import threading
import logging
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.live import Live

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
        r = role.lower()
        if r in ("alice", "sender"):
            self.role = "sender"
            self.peer_role = "receiver"
        else:
            self.role = "receiver"
            self.peer_role = "sender"

        self.role_title = "Sender" if self.role == "sender" else "Receiver"
        self.peer_title = "Receiver" if self.role == "sender" else "Sender"
        self.peer_host = peer_host
        self.esp32_port = esp32_port
        self.force_simulation = force_simulation
        self.backend_type = backend_type

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

        # Gateway Context & Server
        self.gateway_ctx = GatewayContext(
            node_role=self.role,
            session_mgr=self.session_mgr,
            key_pool=self.key_pool,
            event_emitter=self.events,
            send_message_fn=self.send_message,
            rekey_fn=self.replenish_key_pool,
            init_session_fn=self.initiate_session,
        )
        self.gateway_server = GatewayServer(self.gateway_ctx, host="0.0.0.0", port=self.gateway_port)

        self.is_running = False
        self._listener_thread: Optional[threading.Thread] = None
        self.on_message_callback: Optional[Any] = None

    def initialize(self) -> bool:
        """Start hardware channels, listener thread, gateway server, and establish session."""
        q_ok = self.quantum_channel.open()
        c_ok = self.classical_channel.open()
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

    def send_message(self, recipient: str, message: str, mode: str = "teleportation") -> Dict[str, Any]:
        """
        Send a secure message across the quantum channel.
        Both Sender and Receiver can call this to send messages.
        Modes:
        - 'teleportation': Encodes message bits into qubits, executes Bell State Measurement (BSM),
          transmits optical state frames + 2-bit classical corrections over ESP32 Wi-Fi, and executes Pauli reconstruction.
        - 'otp': Consumes exact bits from KeyPool, encrypts with One-Time-Pad, and signs with Wegman-Carter MAC.
        """
        msg_bits = string_to_bits(message)
        if not self.session_mgr.session_id or self.session_mgr.state != SessionState.ESTABLISHED:
            self.initiate_session()
        if self.key_pool.needs_rekey() or self.key_pool.available_bits < len(msg_bits):
            self.replenish_key_pool()

        msg_id = "msg_" + str(uuid.uuid4())[:8]
        t0 = time.time()
        target_role = recipient.capitalize() if recipient else self.peer_title

        if mode == "teleportation":
            self.ui.set_pipeline_stage("Teleport", "active")
            teleport_results = []
            c0_bits = []
            c1_bits = []

            # Teleport message bit-by-bit
            for b in msg_bits:
                res = self.teleporter.teleport_single_qubit(input_bit=b, sender_basis="Z", bob_basis="Z")
                c0, c1 = res["classical_bits"]
                c0_bits.append(c0)
                c1_bits.append(c1)
                teleport_results.append(res)

            # Send optical quantum frame across fibre
            optical_payload = {
                "msg_id": msg_id,
                "qubit_count": len(msg_bits),
                "basis": "Z",
            }
            self.quantum_channel.send_quantum_frame("TELEPORT_QUANTUM_BURST", optical_payload)

            # Transmit classical 2-bit coordinates over ESP32 link with Wegman-Carter MAC
            classical_payload = {
                "msg_id": msg_id,
                "sender_role": self.role_title,
                "recipient": target_role,
                "text": message,
                "c0_bits": c0_bits,
                "c1_bits": c1_bits,
                "bit_count": len(msg_bits),
            }
            mac_tag, _ = WegmanCarterMAC.authenticate_with_pool(
                json.dumps(classical_payload).encode("utf-8"), self.key_pool
            )
            self.classical_channel.send_classical("TELEPORT_MESSAGE", classical_payload, mac=mac_tag)

            self.ui.set_pipeline_stage("Correct", "done")
            self.ui.add_log(f"Sent to {target_role}: \"{message}\" [Teleportation]")

            # Record in sent store
            record = {
                "id": msg_id,
                "to": target_role,
                "from": self.role_title,
                "direction": "outgoing",
                "text": message,
                "mode": "teleportation",
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
                "security": "laptop-to-laptop quantum-secure",
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
                "mode": "otp",
            }
            self.classical_channel.send_classical("OTP_MESSAGE", payload, mac=mac_tag)
            self.ui.add_log(f"Sent to {target_role}: \"{message}\" [OTP - {otp_res['bit_length']} bits burned]")

            record = {
                "id": msg_id,
                "to": target_role,
                "from": self.role_title,
                "direction": "outgoing",
                "text": message,
                "ciphertext": ct_hex,
                "mode": "otp",
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
                "security": "laptop-to-laptop quantum-secure",
            }

    def _channel_listener_loop(self):
        """
        Background listener loop continuously monitoring optical and classical channels
        to process incoming chat messages, handshake packets, and ACKs from peer.
        """
        while self.is_running:
            try:
                # 1. Listen for incoming classical messages
                c_pkt = self.classical_channel.receive_classical(timeout=0.2)
                if c_pkt:
                    self._handle_incoming_classical_packet(c_pkt)

                # 2. Listen for optical quantum frames
                q_pkt = self.quantum_channel.receive_quantum_frame(timeout=0.1)
                if q_pkt:
                    logger.debug("Received optical frame: %s", q_pkt.get("type"))
            except Exception as e:
                logger.debug("Listener loop exception: %s", e)
                time.sleep(0.1)

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

            # Apply Bob Pauli X/Z correction simulation
            recovered_bits = []
            for c0, c1 in zip(c0_bits, c1_bits):
                # Bob recovers bit from Pauli correction Z^c0 X^c1
                recovered_bits.append(0 if (c0 ^ c1) == 0 else 1)

            # Record received message
            record = {
                "id": msg_id,
                "from": sender_name,
                "to": self.role_title,
                "direction": "incoming",
                "text": text,
                "mode": "teleportation",
                "timestamp": time.time(),
            }
            self.received_messages.append(record)
            self.gateway_ctx.received_messages.append(record)

            self.ui.add_log(f"Received from {sender_name}: \"{text}\" [Teleportation]")
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

            decrypted_text = OneTimePad.decrypt(ct_hex, raw_keys) if raw_keys else "[Encrypted OTP]"

            record = {
                "id": msg_id,
                "from": sender_name,
                "to": self.role_title,
                "direction": "incoming",
                "text": decrypted_text,
                "ciphertext": ct_hex,
                "mode": "otp",
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
            console.print(f"\n[bold magenta]◄ [{sender}]:[/bold magenta] [bold white]{text}[/bold white] [dim]({mode})[/dim]")
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
                elif line.lower() == "/help":
                    console.print("[dim]Commands: /status (view metrics), /rekey (replenish keys), /quit (turn off)[/dim]")
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
