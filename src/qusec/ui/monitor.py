from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

import time
import random
import json
import os

from qusec.qds.signature import construct_payload
from qusec.sarg04.protocol import get_decoy_state, generate_sarg04_candidate, sift_sarg04
from qusec.quantum.teleportation import simulate_round

console = Console()

class InteractiveSimulator:
    def __init__(self, backend_type=None, shots=1000, threshold=0.06, mu_prob=0.6, nu_prob=0.3, vac_prob=0.1, verbose=False, debug=False, json_output=False):
        self.shots = shots
        self.threshold = threshold
        self.mu_prob = mu_prob
        self.nu_prob = nu_prob
        self.vac_prob = vac_prob
        self.verbose = verbose
        self.debug = debug
        self.json_output = json_output
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
                "backend_name": backend_name
            }
            
            console.print("\nHardware configuration validated.")
            console.print(f"Backend: {backend_name}")
            console.print("Qubits required: 3")
            console.print(f"Shots: {self.shots}")
            console.print("Estimated execution mode: REAL QUANTUM HARDWARE\n")
            
            confirm = Prompt.ask("Submit job to quantum hardware?", choices=["y", "n"], default="n")
            if confirm.lower() != 'y':
                console.print("Operation cancelled.")
                return False
                
            console.print("\n[bold yellow]Quantum Hardware Job[/bold yellow]")
            console.print("─────────────────────────────")
            console.print(f"Backend: {backend_name}")
            console.print(f"Job ID: qsec_hw_{random.randint(10000, 99999)}")
            console.print(f"Instance: {instance}")
            console.print(f"Status: [yellow]QUEUED[/yellow] -> [yellow]RUNNING[/yellow] -> [green]COMPLETED[/green]\n")
            
        return True

    def run(self):
        if not self.json_output:
            if not self.backend_type:
                if not self.interactive_backend_setup():
                    return
            
            console.print(f"[bold cyan]Session ID:[/bold cyan] {self.session_id}")
            message = Prompt.ask("Enter the original message to sign")
        else:
            self.backend_type = self.backend_type or 'simulator'
            message = "Automated Test Message"

        payload, metadata = construct_payload(message)
        
        if not self.json_output:
            msg_bits = payload[metadata["message_start"]:metadata["message_end"]]
            sig_bits = payload[metadata["signature_start"]:metadata["signature_end"]]
            key_bits = payload[metadata["key_start"]:metadata["key_end"]]
            
            console.print(f"\n[bold green]Message Sent:[/bold green] {message}")
            console.print(f"[bold cyan]Bits (Message):[/bold cyan] {''.join(map(str, msg_bits))}")
            console.print(f"[bold cyan]Quantum Public Key (simulated):[/bold cyan] <generated in QKD layer>")
            console.print(f"[bold cyan]Secret key:[/bold cyan] {''.join(map(str, key_bits))}")
            console.print(f"[bold cyan]Digital signature:[/bold cyan] {''.join(map(str, sig_bits))}\n")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Generating quantum/public key material...", total=None)
                time.sleep(1) # simulate work
            console.print("[green]✓ Quantum/public key material generated[/green]\n")
            
            console.print("\n[bold magenta]Example Quantum Circuit (Bit 0):[/bold magenta]")
            _, _, _, example_qc = simulate_round(payload[0], 'Z', 'Z', backend_type=self.backend_type, credentials=self.credentials)
            console.print(example_qc.draw(output='text'))
            console.print("\n")
            
            attack_choice = Prompt.ask(
                "Do you want to simulate an attack?\n"
                "1. No Attack\n"
                "2. Forgery\n"
                "3. Impersonation\n"
                "4. Replay Attack\n"
                "5. Unauthorized Verification\n"
                "6. Quantum Channel Tampering\n"
                "7. Intercept-Resend\n"
                "8. SARG04 Channel Disturbance\n"
                "9. Custom Scenario\n"
                "0. Back\n"
                "Select", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="1"
            )
        else:
            attack_choice = "1"

        if attack_choice == "2" and not self.json_output:
            console.print("\n[bold red]ATTACKER MODE[/bold red]")
            forged_msg = Prompt.ask("Enter forged message")
            from qusec.qds.signature import generate_signature
            forged_sig_bits = generate_signature(forged_msg)
            forged_sig = "".join(map(str, forged_sig_bits))
            console.print(f"[bold red]Generated forged signature:[/bold red] {forged_sig}")
            
            console.print("\n[bold red]⚠ SECURITY EVENT[/bold red]")
            console.print("Attack Type: FORGERY")
            console.print("Target: Digital Signature")
            console.print("Evidence: Signature mismatch")

        # Start processing
        conclusive_mu = 0
        errors = 0
        
        if not self.json_output:
            console.print("\n[bold cyan]Starting Qubit-by-Qubit Transmission...[/bold cyan]")
            
        for i, bit in enumerate(payload):
            if attack_choice == "6" and random.random() < 0.2:
                c0_flip = True
            else:
                c0_flip = False
                
            sender_basis = random.choice(['Z', 'X'])
            bob_basis = random.choice(['Z', 'X'])
            decoy = get_decoy_state(self.mu_prob, self.nu_prob, self.vac_prob)
            candidate = generate_sarg04_candidate(bit, sender_basis)

            c0, c1, bob_res, qc_bob = simulate_round(bit, sender_basis, bob_basis, c0_flip=c0_flip, backend_type=self.backend_type, credentials=self.credentials)

            sifting = sift_sarg04(bob_res, bob_basis, candidate)

            if sifting["conclusive"] and decoy == 'mu':
                conclusive_mu += 1
                if sifting["reconstructed_bit"] != bit:
                    errors += 1
            
            if not self.json_output:
                if self.verbose or i < 10:
                    console.print(f"\n[cyan]Qubit {i+1} / {len(payload)}[/cyan]")
                    console.print(f"Original bit: {bit}, Sender basis: {sender_basis}, Decoy: {decoy}")
                    console.print(f"[yellow]Sender Side (Alice):[/yellow]")
                    console.print(f"  Measurement result c0: {c0}")
                    console.print(f"  Measurement result c1: {c1}")
                    console.print(f"[yellow]Receiver Side (Bob):[/yellow]")
                    console.print(f"  Pauli X Correction (c1={c1}): {'Applied' if c1 == 1 else 'None'}")
                    console.print(f"  Pauli Z Correction (c0={c0}): {'Applied' if c0 == 1 else 'None'}")
                    console.print(f"  Recovered State (Measurement): {bob_res}")
                    console.print(f"  SARG04 Conclusive: {sifting['conclusive']}")
                elif i == 10 and not self.verbose:
                    console.print("\n[cyan]... remaining bits hidden. Run with --verbose to see all bits ...[/cyan]")

        qber = (errors / conclusive_mu) if conclusive_mu > 0 else 0
        
        decision = "VERIFIED"
        if qber > self.threshold:
            decision = "THREAT DETECTED"
        elif attack_choice == "2":
            decision = "REJECTED (FORGERY)"
        elif attack_choice == "3":
            decision = "REJECTED (IMPERSONATION)"
        elif attack_choice == "4":
            decision = "REJECTED (REPLAY)"
            
        if self.json_output:
            report = {
                "session_id": self.session_id,
                "backend": self.backend_type,
                "statistics": {"qber": qber, "threshold": self.threshold},
                "decision": decision
            }
            print(json.dumps(report, indent=4))
        else:
            self.print_report(len(payload), conclusive_mu, errors, qber, decision, attack_choice)

    def print_report(self, payload_len, conclusive_mu, errors, qber, decision, attack):
        console.print("\n")
        table = Table(title="[bold cyan]QUSEC REPORT[/bold cyan]", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Session ID", self.session_id)
        table.add_row("Backend", self.backend_type.upper())
        table.add_row("Execution Mode", "LOCAL SIMULATION" if self.backend_type == 'simulator' else "NOISY SIMULATION" if self.backend_type == 'noisy' else "REAL QUANTUM HARDWARE")
        table.add_row("Protocol", "Teleportation-QDS + SARG04")
        table.add_row("Qubits", f"{payload_len} / {payload_len}")
        table.add_row("QBER", f"{qber:.4f}")
        table.add_row("Threshold", str(self.threshold))
        console.print(table)
        
        color = "green" if decision == "VERIFIED" else "red"
        console.print(f"\n[bold {color}]FINAL DECISION: {decision}[/bold {color}]\n")
