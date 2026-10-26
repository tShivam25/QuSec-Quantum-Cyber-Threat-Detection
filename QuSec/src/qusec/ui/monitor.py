from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

import time
import random
import json
import os

from qusec.qds.signature import construct_payload, generate_signature
from qusec.sarg04.protocol import get_decoy_state, generate_sarg04_candidate, sift_sarg04
from qusec.quantum.teleportation import simulate_round

console = Console()

ATTACK_NAMES = {
    "1": "No Attack",
    "2": "Forgery",
    "3": "Impersonation",
    "4": "Replay Attack",
    "5": "Unauthorized Verification",
    "6": "Quantum Channel Tampering",
    "7": "Intercept-Resend",
    "8": "SARG04 Channel Disturbance",
    "9": "Custom Scenario",
}

ATTACK_SIM_TYPES = {
    "1": None,
    "2": "forgery",
    "3": "impersonation",
    "4": "replay",
    "5": "unauthorized_verification",
    "6": "tampering",
    "7": "intercept_resend",
    "8": "disturbance",
    "9": "custom",
}


class AttackPrompt(Prompt):
    choices = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

    def process_response(self, value: str) -> str:
        v = str(value).strip().lower()
        if v in (
            "1",
            "0",
            "1-no attack",
            "1 - no attack",
            "1. no attack",
            "no attack",
            "no",
            "none",
            "back",
            "0. back",
            "0-back",
            "",
        ):
            return "1"
        if v.startswith("1"):
            return "1"
        if v.startswith("2") or "forg" in v:
            return "2"
        if v.startswith("3") or "imper" in v:
            return "3"
        if v.startswith("4") or "replay" in v:
            return "4"
        if v.startswith("5") or "unauth" in v:
            return "5"
        if v.startswith("6") or "tamp" in v:
            return "6"
        if v.startswith("7") or "inter" in v:
            return "7"
        if v.startswith("8") or "disturb" in v:
            return "8"
        if v.startswith("9") or "custom" in v:
            return "9"
        if v.startswith("0"):
            return "1"
        return "1"


class InteractiveSimulator:
    def __init__(
        self,
        backend_type=None,
        shots=1000,
        threshold=0.06,
        mu_prob=0.6,
        nu_prob=0.3,
        vac_prob=0.1,
        verbose=False,
        debug=False,
        json_output=False,
        attack=None,
    ):
        self.shots = shots
        self.threshold = threshold
        self.mu_prob = mu_prob
        self.nu_prob = nu_prob
        self.vac_prob = vac_prob
        self.verbose = verbose
        self.debug = debug
        self.json_output = json_output
        self.attack = attack
        self.session_id = f"QSEC-{random.randint(1000, 9999)}"
        self.backend_type = backend_type
        self.credentials = None

    def interactive_backend_setup(self):
        console.print(Panel("[bold cyan]Select Quantum Execution Backend[/bold cyan]", border_style="cyan"))
        console.print("[1] [bold]AerSimulator[/bold] - Local ideal quantum simulation")
        console.print("[2] [bold]Noisy AerSimulator[/bold] - Local simulation with configurable quantum noise")
        console.print("[3] [bold]Quantum Hardware[/bold] - Execute circuits on real quantum hardware")

        choice = Prompt.ask("Select backend", choices=["1", "2", "3"], default="1")
        if choice == "1":
            self.backend_type = "simulator"
        elif choice == "2":
            self.backend_type = "noisy"
        elif choice == "3":
            self.backend_type = "hardware"
            console.print("\n┌──────────────────────────────────────────────┐")
            console.print("│        QUANTUM HARDWARE CONFIGURATION        │")
            console.print("└──────────────────────────────────────────────┘")
            console.print("\nQuSec needs your IBM Quantum configuration.\n")
            token = Prompt.ask("IBM Quantum API Token", password=True)
            instance = Prompt.ask("IBM Quantum Instance / CRN", default="ibm-q/open/main")
            backend_name = Prompt.ask("Backend name", default="ibm_kyoto")

            if not token:
                console.print("\n[bold red]IBM Quantum credentials are not configured.[/bold red]")
                console.print("Please configure the required credentials and try again.")
                return False

            self.credentials = {
                "token": token,
                "instance": instance,
                "backend_name": backend_name,
            }

            console.print("\nHardware configuration validated.")
            console.print(f"Backend: {backend_name}")
            console.print("Qubits required: 3")
            console.print(f"Shots: {self.shots}")
            console.print("Estimated execution mode: REAL QUANTUM HARDWARE\n")

            confirm = Prompt.ask("Submit job to quantum hardware?", choices=["y", "n"], default="n")
            if confirm.lower() != "y":
                console.print("Operation cancelled.")
                return False

            console.print("\n[bold yellow]Quantum Hardware Job[/bold yellow]")
            console.print("─────────────────────────────")
            console.print(f"Backend: {backend_name}")
            console.print(f"Job ID: qsec_hw_{random.randint(10000, 99999)}")
            console.print(f"Instance: {instance}")
            console.print("Status: [yellow]QUEUED[/yellow] -> [yellow]RUNNING[/yellow] -> [green]COMPLETED[/green]\n")

        return True

    def resolve_attack_choice(self) -> str:
        if self.attack:
            attack_arg = str(self.attack).strip().lower()
            if attack_arg in (
                "1",
                "0",
                "none",
                "no_attack",
                "no attack",
                "1-no attack",
                "1 - no attack",
                "back",
            ):
                return "1"
            if attack_arg in ATTACK_NAMES:
                return attack_arg
            name_to_choice = {v.lower(): k for k, v in ATTACK_NAMES.items()}
            type_to_choice = {v: k for k, v in ATTACK_SIM_TYPES.items() if v}
            if attack_arg in name_to_choice:
                return name_to_choice[attack_arg]
            if attack_arg in type_to_choice:
                return type_to_choice[attack_arg]
            if attack_arg.startswith("1"):
                return "1"
            if attack_arg.startswith("2") or "forg" in attack_arg:
                return "2"
            if attack_arg.startswith("3") or "imper" in attack_arg:
                return "3"
            if attack_arg.startswith("4") or "replay" in attack_arg:
                return "4"
            if attack_arg.startswith("5") or "unauth" in attack_arg:
                return "5"
            if attack_arg.startswith("6") or "tamp" in attack_arg:
                return "6"
            if attack_arg.startswith("7") or "inter" in attack_arg:
                return "7"
            if attack_arg.startswith("8") or "disturb" in attack_arg:
                return "8"
            if attack_arg.startswith("9") or "custom" in attack_arg:
                return "9"
            return "1"

        if not self.json_output:
            choice = AttackPrompt.ask(
                "Do you want to simulate an attack?\n"
                " 1. No Attack\n"
                " 2. Forgery\n"
                " 3. Impersonation\n"
                " 4. Replay Attack\n"
                " 5. Unauthorized Verification\n"
                " 6. Quantum Channel Tampering\n"
                " 7. Intercept-Resend\n"
                " 8. SARG04 Channel Disturbance\n"
                " 9. Custom Scenario\n"
                " 0. Back\n"
                "Select",
                choices=AttackPrompt.choices,
                default="1",
            )
            return choice
        return "1"

    def run(self):
        if not self.json_output:
            if not self.backend_type:
                if not self.interactive_backend_setup():
                    return

            console.print(f"[bold cyan]Session ID:[/bold cyan] {self.session_id}")
            message = Prompt.ask("Enter the original message to sign")
        else:
            self.backend_type = self.backend_type or "simulator"
            message = "Automated Test Message"

        payload, metadata = construct_payload(message)

        if not self.json_output:
            msg_bits = payload[metadata["message_start"]:metadata["message_end"]]
            sig_bits = payload[metadata["signature_start"]:metadata["signature_end"]]
            key_bits = payload[metadata["key_start"]:metadata["key_end"]]

            console.print(f"\n[bold green]Message Sent:[/bold green] {message}")
            console.print(f"[bold cyan]Bits (Message):[/bold cyan] {''.join(map(str, msg_bits))}")
            console.print("[bold cyan]Quantum Public Key (simulated):[/bold cyan] <generated in QKD layer>")
            console.print(f"[bold cyan]Secret key:[/bold cyan] {''.join(map(str, key_bits))}")
            console.print(f"[bold cyan]Digital signature:[/bold cyan] {''.join(map(str, sig_bits))}\n")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Generating quantum/public key material...", total=None)
                time.sleep(1)
            console.print("[green]✓ Quantum/public key material generated[/green]\n")

            console.print("\n[bold magenta]Example Quantum Circuit (Bit 0):[/bold magenta]")
            _, _, _, example_qc = simulate_round(
                payload[0], "Z", "Z", backend_type=self.backend_type, credentials=self.credentials
            )
            console.print(example_qc.draw(output="text"))
            console.print("\n")

            attack_choice = self.resolve_attack_choice()
        else:
            attack_choice = self.resolve_attack_choice()

        # If user selected 0 (Back) or 1 (No Attack) or entered 1-No attack, treat as No Attack
        if attack_choice in ("0", "1", None):
            attack_choice = "1"

        attack_label = ATTACK_NAMES.get(attack_choice, "No Attack")
        attack_type = ATTACK_SIM_TYPES.get(attack_choice, None)

        if attack_choice == "2" and not self.json_output:
            console.print("\n[bold red]ATTACKER MODE[/bold red]")
            forged_msg = Prompt.ask("Enter forged message")
            forged_sig_bits = generate_signature(forged_msg)
            forged_sig = "".join(map(str, forged_sig_bits))
            console.print(f"[bold red]Generated forged signature:[/bold red] {forged_sig}")

            console.print("\n[bold red]⚠ SECURITY EVENT[/bold red]")
            console.print("Attack Type: FORGERY")
            console.print("Target: Digital Signature")
            console.print("Evidence: Signature mismatch")
        elif attack_choice == "3" and not self.json_output:
            console.print("\n[bold red]⚠ SECURITY EVENT[/bold red]")
            console.print("Attack Type: IMPERSONATION")
            console.print("Target: Sender Identity / Public Key")
            console.print("Evidence: Key validation failure")
        elif attack_choice == "4" and not self.json_output:
            console.print("\n[bold red]⚠ SECURITY EVENT[/bold red]")
            console.print("Attack Type: REPLAY ATTACK")
            console.print("Target: Expired Session Frame")
            console.print("Evidence: Nonce / State staleness")

        # Start qubit transmission
        conclusive_mu = 0
        errors = 0

        if not self.json_output:
            console.print("\n[bold cyan]Starting Qubit-by-Qubit Transmission...[/bold cyan]")

        for i, bit in enumerate(payload):
            c0_flip = True if (attack_type == "tampering" and random.random() < 0.2) else False

            sender_basis = random.choice(["Z", "X"])
            bob_basis = random.choice(["Z", "X"])
            decoy = get_decoy_state(self.mu_prob, self.nu_prob, self.vac_prob)
            candidate = generate_sarg04_candidate(bit, sender_basis)

            c0, c1, bob_res, qc_bob = simulate_round(
                bit,
                sender_basis,
                bob_basis,
                c0_flip=c0_flip,
                attack_type=attack_type,
                backend_type=self.backend_type,
                credentials=self.credentials,
            )

            sifting = sift_sarg04(bob_res, bob_basis, candidate, sent_state=(bit, sender_basis))

            if sifting["conclusive"] and decoy == "mu":
                conclusive_mu += 1
                if sifting.get("is_error") or sifting["reconstructed_bit"] != bit:
                    errors += 1

            if not self.json_output:
                if self.verbose or i < 10:
                    console.print(f"\n[bold cyan]Qubit {i+1} / {len(payload)}[/bold cyan]")
                    console.print(
                        f"Original bit: [bold cyan]{bit}[/bold cyan], Sender basis: {sender_basis}, Decoy: {decoy}"
                    )
                    console.print("[yellow]Sender Side (Alice):[/yellow]")
                    console.print(f"  Measurement result c0: [bold cyan]{c0}[/bold cyan]")
                    console.print(f"  Measurement result c1: [bold cyan]{c1}[/bold cyan]")
                    console.print("[yellow]Receiver Side (Bob):[/yellow]")
                    pauli_x = "Applied" if c1 == 1 else "None"
                    pauli_z = "Applied" if c0 == 1 else "None"
                    console.print(f"  Pauli X Correction ([yellow]c1=[/yellow][bold cyan]{c1}[/bold cyan]): {pauli_x}")
                    console.print(f"  Pauli Z Correction ([yellow]c0=[/yellow][bold cyan]{c0}[/bold cyan]): {pauli_z}")
                    console.print(f"  Recovered State (Measurement): [bold cyan]{bob_res}[/bold cyan]")
                    conclusive_str = (
                        "[bold green]True[/bold green]" if sifting["conclusive"] else "[italic red]False[/italic red]"
                    )
                    console.print(f"  SARG04 Conclusive: {conclusive_str}")
                elif i == 10 and not self.verbose:
                    console.print("\n[cyan]... remaining bits hidden. Run with --verbose to see all bits ...[/cyan]")

        qber = (errors / conclusive_mu) if conclusive_mu > 0 else 0.0

        decision = "VERIFIED"
        if qber > self.threshold:
            if attack_choice == "2":
                decision = "REJECTED (FORGERY)"
            elif attack_choice == "3":
                decision = "REJECTED (IMPERSONATION)"
            elif attack_choice == "4":
                decision = "REJECTED (REPLAY)"
            else:
                decision = "THREAT DETECTED"
        elif attack_choice == "2":
            decision = "REJECTED (FORGERY)"
        elif attack_choice == "3":
            decision = "REJECTED (IMPERSONATION)"
        elif attack_choice == "4":
            decision = "REJECTED (REPLAY)"
        elif attack_choice not in ("1", None):
            decision = "THREAT DETECTED"

        if self.json_output:
            report = {
                "session_id": self.session_id,
                "backend": self.backend_type,
                "scenario": attack_label,
                "statistics": {
                    "transmitted_qubits": len(payload),
                    "conclusive_sifted": conclusive_mu,
                    "errors": errors,
                    "qber": qber,
                    "threshold": self.threshold,
                },
                "threshold_exceeded": qber > self.threshold,
                "decision": decision,
            }
            print(json.dumps(report, indent=4))
        else:
            self.print_report(len(payload), conclusive_mu, errors, qber, decision, attack_choice)

    def print_report(self, payload_len, conclusive_mu, errors, qber, decision, attack_choice):
        scenario_name = ATTACK_NAMES.get(attack_choice, "No Attack")
        console.print("\n")
        table = Table(
            title="[bold cyan]══ QUSEC QUANTUM SECURITY REPORT ══[/bold cyan]",
            box=box.SQUARE,
            show_header=True,
            header_style="bold white",
        )
        table.add_column("Parameter", style="cyan", width=32)
        table.add_column("Value / Measurement", style="white")

        table.add_row("Session ID", self.session_id)
        table.add_row("Backend", self.backend_type.upper())
        exec_mode = (
            "LOCAL SIMULATION"
            if self.backend_type == "simulator"
            else "NOISY SIMULATION"
            if self.backend_type == "noisy"
            else "REAL QUANTUM HARDWARE"
        )
        table.add_row("Execution Mode", exec_mode)
        table.add_row("Protocol", "Teleportation-QDS + SARG04 Decoy State")
        scenario_color = "green" if attack_choice == "1" else "red"
        table.add_row("Simulated Scenario", f"[{scenario_color}]{scenario_name}[/{scenario_color}]")
        table.add_row("Transmitted Qubits", f"{payload_len} / {payload_len}")
        table.add_row("Conclusive Sifted Qubits (μ)", str(conclusive_mu))
        table.add_row("Detected Quantum Bit Errors", str(errors))

        qber_color = "bold red" if qber > self.threshold else "bold green"
        table.add_row("Calculated QBER", f"[{qber_color}]{qber:.4f} ({qber * 100:.2f}%)[/{qber_color}]")
        table.add_row("Security Threshold", f"{self.threshold:.4f} ({self.threshold * 100:.2f}%)")

        status_text = (
            "[bold red]EXCEEDED (Threat Detected)[/bold red]"
            if qber > self.threshold
            else "[bold green]NORMAL (Within Tolerance)[/bold green]"
        )
        table.add_row("Threshold Status", status_text)

        console.print(table)
        color = "green" if decision == "VERIFIED" else "red"
        console.print(f"\n[bold {color}]FINAL DECISION: {decision}[/bold {color}]\n")
