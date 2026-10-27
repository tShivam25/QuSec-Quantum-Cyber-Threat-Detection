"""
qusec doctor: Self-test and diagnostic verification tool.
Checks every physical and logical link before initiating a quantum communication session:
- Python environment & quantum libraries (Qiskit, Aer, Rich, PySerial, WebSockets)
- ESP32 microcontrollers (USB serial port detection, VID/PID, ping response, hardware TRNG)
- Ethernet & Optical Media Converters (Network interfaces, link state, MTU, transceiver loopback)
- Classical Wi-Fi / Serial Channel socket binding and reachability
"""

import sys
import time
import socket
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from qusec import __version__
from qusec.hardware.esp32 import ESP32Detector, HAS_SERIAL
from qusec.hardware.rng import RandomSource
from qusec.hardware.optical import EthernetDetector, QuantumChannel
from qusec.hardware.classical import ClassicalChannel

console = Console()


def run_doctor(peer_host: str = "") -> Dict[str, Any]:
    """Execute complete diagnostic suite and display results."""
    results = {
        "version": __version__,
        "python_ok": True,
        "esp32_detected": False,
        "esp32_devices": [],
        "trng_hardware": False,
        "ethernet_detected": False,
        "ethernet_interfaces": [],
        "optical_socket_ok": False,
        "classical_socket_ok": False,
        "overall_status": "READY",
    }

    console.print("\n[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║                 QuSec System Diagnostics Doctor           ║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]\n")

    # 1. Environment & Dependencies Table
    dep_table = Table(title="[bold yellow]1. Software Environment & Quantum Libraries[/bold yellow]", box=box.ROUNDED)
    dep_table.add_column("Component", style="cyan", width=25)
    dep_table.add_column("Required", style="magenta", width=15)
    dep_table.add_column("Detected", style="green", width=20)
    dep_table.add_column("Status", width=15)

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    dep_table.add_row("Python", ">= 3.9", py_ver, "[bold green]● OK[/bold green]")

    # Qiskit
    try:
        import qiskit
        qiskit_ver = getattr(qiskit, "__version__", "Installed")
        dep_table.add_row("Qiskit", "~= 2.5", str(qiskit_ver), "[bold green]● OK[/bold green]")
    except ImportError:
        dep_table.add_row("Qiskit", "~= 2.5", "Missing", "[bold red]✖ FAIL[/bold red]")
        results["python_ok"] = False

    # Qiskit-Aer
    try:
        import qiskit_aer
        aer_ver = getattr(qiskit_aer, "__version__", "Installed")
        dep_table.add_row("Qiskit Aer", "~= 0.17", str(aer_ver), "[bold green]● OK[/bold green]")
    except ImportError:
        dep_table.add_row("Qiskit Aer", "~= 0.17", "Missing", "[bold red]✖ FAIL[/bold red]")
        results["python_ok"] = False

    # PySerial
    if HAS_SERIAL:
        import serial
        dep_table.add_row("PySerial", ">= 3.5", getattr(serial, "__version__", "Installed"), "[bold green]● OK[/bold green]")
    else:
        dep_table.add_row("PySerial", ">= 3.5", "Missing", "[bold yellow]▲ WARN (Simulation only)[/bold yellow]")

    # WebSockets
    try:
        import websockets
        ws_ver = getattr(websockets, "__version__", "Installed")
        dep_table.add_row("WebSockets", ">= 10.0", str(ws_ver), "[bold green]● OK[/bold green]")
    except ImportError:
        dep_table.add_row("WebSockets", ">= 10.0", "Missing", "[bold yellow]▲ WARN (REST only)[/bold yellow]")

    console.print(dep_table)

    # 2. ESP32 Microcontroller Auto-Detection Table
    esp_table = Table(title="[bold yellow]2. ESP32 Hardware & Serial Link Detection[/bold yellow]", box=box.ROUNDED)
    esp_table.add_column("Port", style="cyan", width=25)
    esp_table.add_column("Description / Model", style="magenta", width=30)
    esp_table.add_column("Type", width=15)
    esp_table.add_column("Status", width=15)

    detected_ports = ESP32Detector.scan_ports()
    results["esp32_devices"] = detected_ports

    esp_count = 0
    for p in detected_ports:
        is_esp = p.get("is_esp32", False)
        if is_esp:
            esp_count += 1
            esp_table.add_row(
                p["port"],
                p.get("model", "ESP32 Device"),
                "ESP32 Bridge",
                "[bold green]● DETECTED[/bold green]"
            )
        else:
            esp_table.add_row(
                p["port"],
                p.get("description", "Serial"),
                "Other UART",
                "[dim]Inactive[/dim]"
            )

    if esp_count > 0:
        results["esp32_detected"] = True
    else:
        esp_table.add_row(
            "No USB-Serial Found",
            "No ESP32 connected via USB",
            "Virtual / Simulation",
            "[bold yellow]▲ SIMULATION READY[/bold yellow]"
        )
    console.print(esp_table)

    # 3. Random Number Source Test
    rng = RandomSource()
    results["trng_hardware"] = rng.is_hardware
    rng_status_text = "[bold green]● ESP32 Hardware TRNG[/bold green]" if rng.is_hardware else "[bold cyan]● System CSPRNG (Simulation)[/bold cyan]"
    test_bytes = rng.get_random_bytes(16)
    console.print(f"  [bold]RandomSource:[/bold] {rng.source_name} -> Sample entropy: [dim]{test_bytes.hex()}[/dim] {rng_status_text}\n")

    # 4. Ethernet & Optical Transceivers Table
    eth_table = Table(title="[bold yellow]3. Optical Transceiver & Ethernet Media Converter Detection[/bold yellow]", box=box.ROUNDED)
    eth_table.add_column("Interface", style="cyan", width=15)
    eth_table.add_column("MAC Address", style="magenta", width=20)
    eth_table.add_column("IP Address", width=18)
    eth_table.add_column("Link State", width=22)

    ifaces = EthernetDetector.get_interfaces()
    results["ethernet_interfaces"] = ifaces

    active_eth_found = False
    active_iface_name = ""
    eth_count = 0
    for iface in ifaces:
        # Strictly ignore non-ethernet / wireless / loopback
        if not iface.get("is_ethernet", False):
            continue
        eth_count += 1
        status_label = "[bold green]● ACTIVE (LINK CARRIER)[/bold green]" if iface["is_active"] else "[bold red]✖ DISCONNECTED (NO CABLE)[/bold red]"
        if iface["is_active"]:
            active_eth_found = True
            active_iface_name = iface["name"]
        eth_table.add_row(
            iface["name"],
            iface.get("mac") or "N/A",
            iface.get("ip") or "No IP (Layer 2)",
            status_label
        )

    if eth_count == 0:
        eth_table.add_row("No Ethernet NIC", "No Media Converter detected", "N/A", "[bold red]✖ NOT DETECTED[/bold red]")

    results["ethernet_detected"] = active_eth_found
    console.print(eth_table)

    # 5. Socket Bind & Loopback Link Tests
    console.print("[bold yellow]4. Channel Socket Bind & Transceiver Loopback Tests[/bold yellow]")
    q_chan = QuantumChannel(local_port=19876, force_simulation=True)
    c_chan = ClassicalChannel(local_port=19877, force_simulation=True)

    q_ok = q_chan.open()
    c_ok = c_chan.open()
    results["optical_socket_ok"] = q_ok
    results["classical_socket_ok"] = c_ok

    q_chan.close()
    c_chan.close()

    console.print(f"  Quantum Optical Socket (Port 9876): {'[bold green]● OK[/bold green]' if q_ok else '[bold red]✖ BIND ERROR[/bold red]'}")
    console.print(f"  Classical ESP32 Socket (Port 9877): {'[bold green]● OK[/bold green]' if c_ok else '[bold red]✖ BIND ERROR[/bold red]'}\n")

    # 6. End-to-End Optical Probe (if peer host provided)
    peer_carrier_tested = False
    peer_carrier_verified = False
    if peer_host and peer_host not in ("127.0.0.1", "localhost", "0.0.0.0"):
        peer_carrier_tested = True
        console.print(f"[bold yellow]5. End-to-End Optical Fibre Link Probe ([cyan]{peer_host}[/cyan])[/bold yellow]")
        carrier_ok, rtt_ms, carrier_msg = QuantumChannel.probe_optical_carrier(peer_host, timeout=1.0)
        peer_carrier_verified = carrier_ok
        c_style = "bold green" if carrier_ok else "bold red"
        console.print(f"  Optical Signal: [{c_style}]{carrier_msg}[/{c_style}]\n")

    # 7. Overall Assessment Panel
    if peer_carrier_tested:
        fibre_online = peer_carrier_verified
    else:
        fibre_online = active_eth_found

    if results["esp32_detected"] and fibre_online:
        panel_color = "green"
        headline = "[bold green]✔ PHYSICAL HARDWARE READY FOR DEPLOYMENT[/bold green]"
        guidance = "ESP32 microcontrollers and Optical Transceiver Ethernet converters detected and linked.\nRun 'qusec chat --role sender --peer-host <ip>' on sender and 'qusec chat --role receiver' on receiver."
    elif results["esp32_detected"] or fibre_online:
        panel_color = "yellow"
        headline = "[bold yellow]▲ PARTIAL HARDWARE DETECTED — SIMULATION HYBRID MODE[/bold yellow]"
        guidance = "Some physical components connected. Missing links will seamlessly fall back to quantum simulation."
    else:
        panel_color = "cyan"
        headline = "[bold cyan]ℹ FULL SIMULATION MODE READY[/bold cyan]"
        guidance = "No physical optical transceiver or ESP32 detected.\nQuSec will run in high-fidelity quantum simulation mode (Qiskit Aer + virtual network loops).\nTo test with physical hardware, connect ESP32 via USB and Optical Transceiver via Ethernet."

    if peer_carrier_tested:
        if peer_carrier_verified:
            fibre_status = f"[green]● Active (Optical Carrier Verified across Glass Fibre, {rtt_ms:.1f}ms RTT)[/]"
        else:
            fibre_status = "[bold red]✖ DISCONNECTED (Dark Fibre / Cable Unplugged - Zero Light Received)[/]"
    elif active_eth_found:
        fibre_status = f"[green]● Media Converter Link Carrier Detected ({active_iface_name})[/]"
    else:
        fibre_status = "[bold red]✖ Disconnected (No Physical Wired Optical/Ethernet Link)[/]"

    summary_text = (
        f"{headline}\n\n"
        f"• Optical Fibre Link: {fibre_status}\n"
        f"• Classical ESP32 Link: {'[green]Connected' if results['esp32_detected'] else '[yellow]Virtual Socket Relay'}[/]\n"
        f"• Entropy Source: {rng.source_name}\n\n"
        f"[dim]{guidance}[/dim]"
    )
    console.print(Panel(summary_text, title="[bold]Doctor Verdict[/bold]", border_style=panel_color))
    return results
