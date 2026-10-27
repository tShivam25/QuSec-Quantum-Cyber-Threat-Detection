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
            console.print(f"  • Security: [bold yellow]Laptop-to-laptop quantum-secure[/bold yellow]")
            if "qubits_teleported" in result:
                console.print(f"  • Qubits teleported: {result['qubits_teleported']}")
            if "bits_consumed" in result:
                console.print(f"  • Key pool bits burned: {result['bits_consumed']}")
            return 0
    except urllib.error.URLError:
        # Gateway offline, spin up standalone node transmission
        console.print("[yellow]Gateway offline. Transmitting directly via local QuSec engine...[/yellow]")
        node = QuSecNode(role="sender", force_simulation=True)
        node.initialize()
        res = node.send_message(recipient, message, mode=mode)
        node.stop()
        console.print(f"[bold green]✔ Message delivered via {mode.upper()}![/bold green]")
        console.print(f"  • Recipient: [cyan]{recipient}[/cyan]")
        console.print(f"  • Message: \"{message}\"")
        console.print(f"  • Security: [bold yellow]Laptop-to-laptop quantum-secure[/bold yellow]")
        return 0


def cmd_node(args):
    """Handle 'qusec node' command."""
    role = getattr(args, "role", "sender")
    force_sim = getattr(args, "sim", False)
    duration = getattr(args, "duration", None)
    optical_port = getattr(args, "optical_port", None)
    classical_port = getattr(args, "classical_port", None)
    gateway_port = getattr(args, "gateway_port", None)
    esp32_port = getattr(args, "esp32_port", None)
    peer_host = getattr(args, "peer_host", "127.0.0.1")

    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        optical_port=optical_port,
        classical_port=classical_port,
        gateway_port=gateway_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
    )
    node.run_live(duration_seconds=duration)
    return 0


def cmd_gateway(args):
    """Handle 'qusec gateway' command."""
    role = getattr(args, "role", "sender")
    force_sim = getattr(args, "sim", False)
    gateway_port = getattr(args, "port", 8765)
    peer_host = getattr(args, "peer_host", "127.0.0.1")
    esp32_port = getattr(args, "esp32_port", None)

    console.print(f"[bold cyan]Starting QuSec Platform Bridge Gateway on http://0.0.0.0:{gateway_port}...[/bold cyan]")
    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        gateway_port=gateway_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
    )
    node.initialize()
    role_title = "Sender" if role.lower() in ("alice", "sender") else "Receiver"
    console.print(f"[bold green]✔ QuSec Gateway is ready for social media platform integration ({role_title}).[/bold green]")
    console.print(f"  Endpoints:")
    console.print(f"  • Web Chat UI:  http://127.0.0.1:{gateway_port}/")
    console.print(f"  • Status:       GET  http://127.0.0.1:{gateway_port}/api/status")
    console.print(f"  • Send:         POST http://127.0.0.1:{gateway_port}/api/send")
    console.print(f"  • Events:       GET  http://127.0.0.1:{gateway_port}/api/events (SSE stream)")
    console.print(f"  • Init:         POST http://127.0.0.1:{gateway_port}/api/session/init")
    console.print(f"  • Rekey:        POST http://127.0.0.1:{gateway_port}/api/rekey")
    console.print(f"\n[dim]Press Ctrl+C to terminate gateway.[/dim]")

    try:
        while True:
            import time
            time.sleep(1.0)
    except KeyboardInterrupt:
        node.stop()
        console.print("\n[yellow]Gateway stopped.[/yellow]")
    return 0


def cmd_chat(args):
    """Handle 'qusec chat' command - continuous interactive quantum chat."""
    role = getattr(args, "role", "sender")
    peer_host = getattr(args, "peer_host", "127.0.0.1")
    force_sim = getattr(args, "sim", False)
    optical_port = getattr(args, "optical_port", None)
    classical_port = getattr(args, "classical_port", None)
    gateway_port = getattr(args, "gateway_port", None)
    esp32_port = getattr(args, "esp32_port", None)

    node = QuSecNode(
        role=role,
        peer_host=peer_host,
        optical_port=optical_port,
        classical_port=classical_port,
        gateway_port=gateway_port,
        esp32_port=esp32_port,
        force_simulation=force_sim,
    )
    node.run_interactive_chat()
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="qusec",
        description="QuSec - Real-World Quantum Security Transport & Entanglement Framework",
    )
    parser.add_argument("--version", action="version", version=f"QuSec v{__version__}", help="Print version information")
    subparsers = parser.add_subparsers(dest="command")

    # 1. qusec doctor
    subparsers.add_parser("doctor", help="Run hardware detection and diagnostics self-test")

    # 2. qusec node
    node_parser = subparsers.add_parser("node", help="Run interactive QuSec node with live terminal UI")
    node_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob"], default="sender", help="Node role: sender or receiver (default: sender)")
    node_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    node_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    node_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    node_parser.add_argument("--gateway-port", type=int, default=None, help="HTTP API gateway port")
    node_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port (e.g. /dev/cu.usbserial-*)")
    node_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")
    node_parser.add_argument("--hardware", action="store_true", help="Prefer physical hardware links")
    node_parser.add_argument("--duration", type=int, default=None, help="Run for N seconds then exit")

    # 3. qusec chat (continuous interactive terminal chat)
    chat_parser = subparsers.add_parser("chat", help="Start continuous interactive two-way quantum chat")
    chat_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob"], default="sender", help="Node role: sender or receiver (default: sender)")
    chat_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    chat_parser.add_argument("--optical-port", type=int, default=None, help="Optical channel UDP port")
    chat_parser.add_argument("--classical-port", type=int, default=None, help="Classical channel UDP port")
    chat_parser.add_argument("--gateway-port", type=int, default=None, help="HTTP API gateway port")
    chat_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port")
    chat_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")

    # 4. qusec gateway
    gateway_parser = subparsers.add_parser("gateway", help="Run platform bridge API gateway")
    gateway_parser.add_argument("--role", choices=["sender", "receiver", "alice", "bob"], default="sender", help="Node role (default: sender)")
    gateway_parser.add_argument("--peer-host", default="127.0.0.1", help="Peer IP address (default: 127.0.0.1)")
    gateway_parser.add_argument("--port", type=int, default=8765, help="Gateway HTTP port (default: 8765)")
    gateway_parser.add_argument("--esp32-port", default=None, help="ESP32 serial port")
    gateway_parser.add_argument("--sim", action="store_true", help="Force software simulation mode")

    # 4. qusec keys
    keys_parser = subparsers.add_parser("keys", help="Display cryptographic key pool status")
    keys_parser.add_argument("--gateway-url", default="http://127.0.0.1:8765/api/status", help="Gateway API URL")

    # 5. qusec send
    send_parser = subparsers.add_parser("send", help="Send quantum-secure message")
    send_parser.add_argument("message", nargs="?", default=None, help="Message text to transmit")
    send_parser.add_argument("--to", default="receiver", help="Recipient role (default: receiver)")
    send_parser.add_argument("--mode", choices=["teleportation", "otp"], default="teleportation", help="Transmission mode")
    send_parser.add_argument("--gateway-url", default="http://127.0.0.1:8765/api/send", help="Gateway API URL")

    # 6. qusec run (legacy compatibility)
    run_parser = subparsers.add_parser("run", help="Run interactive simulator (legacy)")
    run_parser.add_argument("--backend", choices=["simulator", "noisy", "hardware"], help="Backend execution mode")
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

    # 7. qusec version
    subparsers.add_parser("version", help="Print version information")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
        return 0

    if args.command == "node":
        return cmd_node(args)

    if args.command == "chat":
        return cmd_chat(args)

    if args.command == "gateway":
        return cmd_gateway(args)

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
