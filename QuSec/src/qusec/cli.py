"""
QuSec Command Line Interface (CLI).
Provides commands:
- qusec doctor: Hardware auto-detection, link verification, and diagnostics.
- qusec node --role alice|bob: Interactive live terminal dashboard node.
- qusec gateway: REST and SSE/WebSocket bridge for social media applications.
- qusec keys: Key pool status and lifecycle statistics.
- qusec send: Quantum-secure transmission via teleportation or OTP.
- qusec run: Interactive simulation suite (legacy compatibility).
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from qusec import __version__
from qusec.ui.banner import print_banner
from qusec.ui.monitor import InteractiveSimulator
from qusec.hardware.doctor import run_doctor
from qusec.node import QuSecNode
from qusec.quantum.backend import normalize_backend_type, get_backend_label

console = Console()


def query_gateway_status(url: str = "http://127.0.0.1:8765/api/status") -> Optional[dict]:
    """Fetch status from running gateway server."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qusec-cli"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def cmd_keys(args):
    """Handle 'qusec keys' command."""
    gateway_url = getattr(args, "gateway_url", "http://127.0.0.1:8765/api/status")
    status = query_gateway_status(gateway_url)

    table = Table(title="[bold yellow]QuSec Cryptographic Key Pool Status[/bold yellow]", box=box.ROUNDED)
    table.add_column("Property", style="cyan", width=25)
    table.add_column("Value", style="green", width=30)

    if status and "key_pool" in status:
        kp = status["key_pool"]
        table.add_row("Node Role", status.get("role", "N/A").capitalize())
        table.add_row("Session ID", status.get("session_id", "N/A"))
        table.add_row("Available Keys", f"{kp.get('available_bits', 0):,} bits ({kp.get('available_bytes', 0):,} bytes)")
        table.add_row("Rekey Threshold", f"{kp.get('rekey_threshold', 512):,} bits")
        table.add_row("Pool Health", f"[bold green]{kp.get('health', 'OPTIMAL')}[/bold green]")
        table.add_row("Total Generated", f"{kp.get('total_generated', 0):,} bits")
        table.add_row("Total Consumed & Burned", f"{kp.get('total_consumed', 0):,} bits")
        table.add_row("Rekey Cycles", str(kp.get("rekey_count", 0)))
        console.print(table)
        console.print(f"\n[dim]Gateway source: {gateway_url}[/dim]")
    else:
        # Standalone local query without gateway
        from qusec.session.key_pool import KeyPool
        kp_local = KeyPool(rekey_threshold=512, target_pool_size=4820)
        table.add_row("Gateway Link", "[yellow]Offline (Showing default pool parameters)[/yellow]")
        table.add_row("Default Capacity", f"{kp_local.target_pool_size:,} bits")
        table.add_row("Rekey Trigger", f"{kp_local.rekey_threshold:,} bits")
        table.add_row("Burn-on-use Zeroization", "[bold green]Active[/bold green]")
        console.print(table)
        console.print("\n[dim]To view active node keys, ensure 'qusec node' or 'qusec gateway' is running.[/dim]")
    return 0


def cmd_send(args):
    """Handle 'qusec send' command."""
    recipient = getattr(args, "to", "receiver")
    message = getattr(args, "message", None)
    mode = getattr(args, "mode", "teleportation")
    gateway_url = getattr(args, "gateway_url", "http://127.0.0.1:8765/api/send")

    if not message:
        console.print("[bold red]Error:[/bold red] Message content is required. Usage: qusec send --to receiver \"Hello Quantum World\"")
        return 1

    payload = {
        "to": recipient,
        "message": message,
        "mode": mode,
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            gateway_url,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "qusec-cli"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            console.print(f"[bold green]✔ Message sent successfully via {mode.upper()}![/bold green]")
            console.print(f"  • Recipient: [cyan]{recipient}[/cyan]")
            console.print(f"  • Message: \"{message}\"")
            if "recipient_public_key" in result:
                console.print(f"  • Receiver Quantum Public Key: [bold green]{result['recipient_public_key']}[/bold green] (Encrypted Payload)")
            if "sender_private_key" in result:
                console.print(f"  • Sender Quantum Private Key: [bold yellow]{result['sender_private_key']}[/bold yellow] (Encrypted Signature)")
            console.print(f"  • Security: [bold yellow]Quantum Asymmetric Public-Key + QDS Signed[/bold yellow]")
            if "qubits_teleported" in result:
                console.print(f"  • Qubits teleported: {result['qubits_teleported']}")
            if "bits_consumed" in result:
                console.print(f"  • Key pool bits burned: {result['bits_consumed']}")
            return 0
    except urllib.error.URLError:
        # Gateway offline, spin up standalone node transmission
        console.print("[yellow]Gateway offline. Transmitting directly via local QuSec engine...[/yellow]")
        backend_type = getattr(args, "backend", "aer")
        node = QuSecNode(role="sender", force_simulation=True, backend_type=backend_type)
        node.initialize()
        res = node.send_message(recipient, message, mode=mode)
        node.stop()
        console.print(f"[bold green]✔ Message delivered via {mode.upper()}![/bold green]")
        console.print(f"  • Recipient: [cyan]{recipient}[/cyan]")
        console.print(f"  • Message: \"{message}\"")
        if "recipient_public_key" in res:
            console.print(f"  • Receiver Quantum Public Key: [bold green]{res['recipient_public_key']}[/bold green] (Encrypted Payload)")
        if "sender_private_key" in res:
            console.print(f"  • Sender Quantum Private Key: [bold yellow]{res['sender_private_key']}[/bold yellow] (Encrypted Signature)")
        console.print(f"  • Security: [bold yellow]Quantum Asymmetric Public-Key + QDS Signed[/bold yellow]")
        return 0


def _resolve_peer_config(args):
    """Resolve role and ports based on --role and --peer arguments for dual-node setups."""
    role = getattr(args, "role", "dual")
    peer = getattr(args, "peer", None)
    gateway_port = getattr(args, "port", None) or getattr(args, "gateway_port", None)
    optical_port = getattr(args, "optical_port", None)
    classical_port = getattr(args, "classical_port", None)
    peer_optical_port = getattr(args, "peer_optical_port", None)
    peer_classical_port = getattr(args, "peer_classical_port", None)

    p_str = str(peer).strip().lower() if peer else ""
    r_str = str(role).strip().lower() if role else ""

    if p_str in ("b", "2", "peer_b", "bob") or r_str in ("receiver", "bob", "peer_b"):
        role = "peer_b"
        gateway_port = gateway_port or 8766
        optical_port = optical_port or 9878
        classical_port = classical_port or 9879
        peer_optical_port = peer_optical_port or 9876
        peer_classical_port = peer_classical_port or 9877
    elif p_str in ("a", "1", "peer_a", "alice") or r_str in ("sender", "alice", "peer_a"):
        role = "peer_a"
        gateway_port = gateway_port or 8765
        optical_port = optical_port or 9876
        classical_port = classical_port or 9877
        peer_optical_port = peer_optical_port or 9878
        peer_classical_port = peer_classical_port or 9879
    else:  # dual / peer default
        role = "dual"
        gateway_port = gateway_port or 8765
        optical_port = optical_port or 9876
        classical_port = classical_port or 9877
        peer_optical_port = peer_optical_port or 9878
        peer_classical_port = peer_classical_port or 9879

    backend_type = getattr(args, "backend", "aer")
    ibm_token = getattr(args, "ibm_token", None)
    if ibm_token:
        os.environ["IBM_QUANTUM_TOKEN"] = ibm_token

    return role, gateway_port, optical_port, classical_port, peer_optical_port, peer_classical_port, backend_type


def cmd_node(args):
    """Handle 'qusec node' command."""
    role, gateway_port, optical_port, classical_port, peer_optical_port, peer_classical_port, backend_type = _resolve_peer_config(args)
    force_sim = getattr(args, "sim", False)
    duration = getattr(args, "duration", None)
    esp32_port = getattr(args, "esp32_port", None)
    peer_host = getattr(args, "peer_host", "127.0.0.1")

    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        optical_port=optical_port,
        classical_port=classical_port,
        gateway_port=gateway_port,
        peer_optical_port=peer_optical_port,
        peer_classical_port=peer_classical_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
        backend_type=backend_type,
    )
    node.run_live(duration_seconds=duration)
    return 0


def cmd_gateway(args):
    """Handle 'qusec gateway' and 'qusec bridge' command - Live Transmission Monitor."""
    role, gateway_port, optical_port, classical_port, peer_optical_port, peer_classical_port, backend_type = _resolve_peer_config(args)
    force_sim = getattr(args, "sim", False)
    peer_host = getattr(args, "peer_host", "127.0.0.1")
    esp32_port = getattr(args, "esp32_port", None)

    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        optical_port=optical_port,
        classical_port=classical_port,
        gateway_port=gateway_port,
        peer_optical_port=peer_optical_port,
        peer_classical_port=peer_classical_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
        backend_type=backend_type,
    )
    node.run_transmission_monitor()
    return 0


def cmd_chat(args):
    """Handle 'qusec chat' command - continuous interactive quantum chat or transmission monitor."""
    role, gateway_port, optical_port, classical_port, peer_optical_port, peer_classical_port, backend_type = _resolve_peer_config(args)
    peer_host = getattr(args, "peer_host", "127.0.0.1")
    force_sim = getattr(args, "sim", False)
    esp32_port = getattr(args, "esp32_port", None)
    is_monitor = getattr(args, "monitor", False) or getattr(args, "no_prompt", False)

    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        optical_port=optical_port,
        classical_port=classical_port,
        gateway_port=gateway_port,
        peer_optical_port=peer_optical_port,
        peer_classical_port=peer_classical_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
        backend_type=backend_type,
    )
    if is_monitor:
        node.run_transmission_monitor()
    else:
        node.run_interactive_chat()
    return 0


def cmd_attack(args):
    """Handle 'qusec attacker' / 'qusec attack' command - Claude Code TUI Adversary."""
    from qusec.attacker import QuSecAttacker
    target_host = getattr(args, "target_host", "127.0.0.1")
    target_classical_port = getattr(args, "target_classical_port", 9877)
    target_optical_port = getattr(args, "target_optical_port", 9876)
    esp32_port = getattr(args, "esp32_port", None)
    force_sim = getattr(args, "sim", False)
    vector = getattr(args, "vector", None) or getattr(args, "attack", None)
    msg = getattr(args, "message", "Quantum attack simulation")
    rate = getattr(args, "rate", 0.35)

    attacker = QuSecAttacker(
        target_host=target_host,
        target_classical_port=target_classical_port,
        target_optical_port=target_optical_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
    )

    if vector:
        if vector in ("tamper", "intercept_resend"):
            res = attacker.inject_qber_disturbance(message=msg, disturbance_rate=rate)
            print(json.dumps(res, indent=2))
        elif vector == "pauli":
            res = attacker.inject_pauli_tampering(message=msg, flip_ratio=rate)
            print(json.dumps(res, indent=2))
        elif vector == "forge":
            res = attacker.inject_forgery(fake_message=msg)
            print(json.dumps(res, indent=2))
        elif vector == "replay":
            res = attacker.inject_replay()
            print(json.dumps(res, indent=2))
        elif vector == "jam":
            res = attacker.inject_jamming_burst(packet_count=20)
            print(json.dumps(res, indent=2))
        attacker.close()
        return 0

    attacker.run_interactive()
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="qusec",
        description="QuSec - Real-World Quantum Security Transport & Entanglement Framework",
    )
    parser.add_argument("--version", action="version", version=f"QuSec v{__version__}", help="Print version information")
    subparsers = parser.add_subparsers(dest="command")

    backend_choices = ["1", "2", "3", "aer", "simulator", "noisy", "hardware"]
    backend_help = "Quantum execution backend: 1. AerSimulator (ideal), 2. Noisy AerSimulator (depolarizing/thermal noise), 3. Quantum Hardware (IBM Quantum Cloud)"

    # 1. qusec doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run hardware detection and diagnostics self-test")
    doctor_parser.add_argument("--peer-host", default="", help="Optional peer optical IP to probe end-to-end fiber carrier (e.g. 192.168.2.2)")

    # 2. qusec node
    node_parser = subparsers.add_parser("node", help="Run interactive QuSec node with live terminal UI")
    node_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob", "peer", "dual", "peer_a", "peer_b"], default="dual", help="Node role: sender, receiver, or dual/peer (default: dual)")
    node_parser.add_argument("--peer", choices=["a", "b", "1", "2"], help="Peer identifier for dual-node setup on same machine (a=Peer A, b=Peer B)")
    node_parser.add_argument("--backend", choices=backend_choices, default="aer", help=backend_help)
    node_parser.add_argument("--ibm-token", default=None, help="IBM Quantum Cloud API token for hardware backend")
    node_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    node_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    node_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    node_parser.add_argument("--gateway-port", type=int, default=None, help="HTTP API gateway port")
    node_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port (e.g. /dev/cu.usbserial-*)")
    node_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")
    node_parser.add_argument("--hardware", action="store_true", help="Prefer physical hardware links")
    node_parser.add_argument("--duration", type=int, default=None, help="Run for N seconds then exit")

    # 3. qusec bridge (Live transmission monitor connected to Shnik website)
    bridge_parser = subparsers.add_parser("bridge", help="Connect terminal to https://shnik-lake.vercel.app, ESP32, and optical link in live dual-mode transmission monitor")
    bridge_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob", "peer", "dual", "peer_a", "peer_b"], default="dual", help="Node role (default: dual)")
    bridge_parser.add_argument("--peer", choices=["a", "b", "1", "2"], help="Peer identifier for dual-node setup on same machine (a=Peer A, b=Peer B)")
    bridge_parser.add_argument("--backend", choices=backend_choices, default="aer", help=backend_help)
    bridge_parser.add_argument("--ibm-token", default=None, help="IBM Quantum Cloud API token for hardware backend")
    bridge_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    bridge_parser.add_argument("--port", type=int, default=None, help="Gateway HTTP port (default: 8765 for Peer A, 8766 for Peer B)")
    bridge_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    bridge_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    bridge_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port")
    bridge_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")

    # 4. qusec chat (continuous interactive terminal chat or monitor)
    chat_parser = subparsers.add_parser("chat", help="Start continuous quantum chat or live transmission monitor")
    chat_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob", "peer", "dual", "peer_a", "peer_b"], default="dual", help="Node role (default: dual)")
    chat_parser.add_argument("--peer", choices=["a", "b", "1", "2"], help="Peer identifier for dual-node setup on same machine (a=Peer A, b=Peer B)")
    chat_parser.add_argument("--backend", choices=backend_choices, default="aer", help=backend_help)
    chat_parser.add_argument("--ibm-token", default=None, help="IBM Quantum Cloud API token for hardware backend")
    chat_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    chat_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    chat_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    chat_parser.add_argument("--gateway-port", type=int, default=None, help="HTTP API gateway port")
    chat_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port")
    chat_parser.add_argument("--monitor", action="store_true", help="Run in Live Transmission Monitor mode without typing in terminal")
    chat_parser.add_argument("--no-prompt", action="store_true", help="Disable terminal message prompt and stream website transmissions")
    chat_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")

    # 5. qusec gateway
    gateway_parser = subparsers.add_parser("gateway", help="Run platform bridge API gateway and transmission monitor")
    gateway_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob", "peer", "dual", "peer_a", "peer_b"], default="dual", help="Node role (default: dual)")
    gateway_parser.add_argument("--peer", choices=["a", "b", "1", "2"], help="Peer identifier for dual-node setup on same machine (a=Peer A, b=Peer B)")
    gateway_parser.add_argument("--backend", choices=backend_choices, default="aer", help=backend_help)
    gateway_parser.add_argument("--ibm-token", default=None, help="IBM Quantum Cloud API token for hardware backend")
    gateway_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    gateway_parser.add_argument("--port", type=int, default=None, help="Gateway HTTP port (default: 8765 for Peer A, 8766 for Peer B)")
    gateway_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    gateway_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    gateway_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port")
    gateway_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")

    # 6. qusec keys
    keys_parser = subparsers.add_parser("keys", help="Display cryptographic key pool status")
    keys_parser.add_argument("--gateway-url", default="http://127.0.0.1:8765/api/status", help="Gateway API URL")

    # 7. qusec send
    send_parser = subparsers.add_parser("send", help="Send quantum-secure message")
    send_parser.add_argument("message", nargs="?", default=None, help="Message text to transmit")
    send_parser.add_argument("--to", default="receiver", help="Recipient role (default: receiver)")
    send_parser.add_argument("--mode", choices=["teleportation", "otp"], default="teleportation", help="Transmission mode")
    send_parser.add_argument("--backend", choices=backend_choices, default="aer", help=backend_help)
    send_parser.add_argument("--gateway-url", default="http://127.0.0.1:8765/api/send", help="Gateway API URL")

    # 8. qusec run (legacy compatibility)
    run_parser = subparsers.add_parser("run", help="Run interactive simulator (legacy)")
    run_parser.add_argument("--backend", choices=backend_choices, default="simulator", help=backend_help)
    run_parser.add_argument("--shots", type=int, default=1000, help="Number of shots for verification")
    run_parser.add_argument("--threshold", type=float, default=0.06, help="QBER threshold")
    run_parser.add_argument(
        "--attack",
        choices=[
            "none", "forgery", "impersonation", "replay", "unauthorized_verification",
            "tampering", "intercept_resend", "disturbance", "custom",
            "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ],
        default=None,
        help="Simulate attack vector directly",
    )
    run_parser.add_argument("--mu-probability", type=float, default=0.6, help="Probability of mu decoy state")
    run_parser.add_argument("--nu-probability", type=float, default=0.3, help="Probability of nu decoy state")
    run_parser.add_argument("--vac-probability", type=float, default=0.1, help="Probability of vacuum decoy state")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    run_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    run_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    # 8. qusec attacker (Claude Code TUI Adversary)
    atk_parser = subparsers.add_parser("attacker", aliases=["attack"], help="Launch QuSec Attacker (Eve) with Claude Code TUI")
    atk_parser.add_argument("--target-host", default="127.0.0.1", help="Target Receiver IP (default: 127.0.0.1 or 192.168.4.2)")
    atk_parser.add_argument("--target-classical-port", type=int, default=9877, help="Target classical UDP port (default: 9877, or 9879 for Bob)")
    atk_parser.add_argument("--target-optical-port", type=int, default=9876, help="Target optical UDP port (default: 9876, or 9878 for Bob)")
    atk_parser.add_argument("--esp32-port", default=None, help="Attacker ESP32 serial port (e.g. COM5 or /dev/ttyUSB*)")
    atk_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")
    atk_parser.add_argument("--vector", "--attack", choices=["tamper", "intercept_resend", "pauli", "forge", "replay", "jam"], default=None, help="Direct attack vector")
    atk_parser.add_argument("--message", default="Quantum attack simulation", help="Message payload")
    atk_parser.add_argument("--rate", type=float, default=0.35, help="Disturbance / error rate (default: 0.35)")

    # 9. qusec version
    subparsers.add_parser("version", help="Print version information")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor(peer_host=getattr(args, "peer_host", ""))
        return 0

    if args.command == "node":
        return cmd_node(args)

    if args.command == "chat":
        return cmd_chat(args)

    if args.command in ("gateway", "bridge"):
        return cmd_gateway(args)

    if args.command in ("attacker", "attack"):
        return cmd_attack(args)

    if args.command == "keys":
        return cmd_keys(args)

    if args.command == "send":
        return cmd_send(args)

    if args.command == "version":
        print(f"QuSec v{__version__}")
        return 0

    if not args.command or args.command == "run":
        if getattr(args, "json", False) is False:
            print_banner()

        simulator = InteractiveSimulator(
            backend_type=getattr(args, "backend", None),
            shots=getattr(args, "shots", 1000),
            threshold=getattr(args, "threshold", 0.06),
            mu_prob=getattr(args, "mu_probability", 0.6),
            nu_prob=getattr(args, "nu_probability", 0.3),
            vac_prob=getattr(args, "vac_probability", 0.1),
            verbose=getattr(args, "verbose", False),
            debug=getattr(args, "debug", False),
            json_output=getattr(args, "json", False),
            attack=getattr(args, "attack", None),
        )
        simulator.run()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
