"""
Quantum Teleportation Engine for QuSec.
Performs Bell State Measurement (BSM) between message qubit and Alice's Bell half,
generates 2 classical bits (c0, c1) for transmission over the ESP32 classical channel,
and executes Bob's Pauli X/Z state correction to reconstruct the exact quantum state.
"""

from typing import Dict, Any, Tuple, Optional
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qusec.quantum.backend import execute_circuit


class QuantumTeleportationEngine:
    """
    Executes end-to-end quantum state teleportation between Alice (Sender)
    and Bob (Receiver) using distributed Bell pairs and ESP32 2-bit classical signaling.
    """

    def __init__(self, backend_type: str = "simulator"):
        self.backend_type = backend_type

    def prepare_and_measure_bsm(
        self,
        input_bit: int,
        basis: str = "Z",
    ) -> Tuple[QuantumCircuit, int, int]:
        """
        Step 1 (Alice):
        Prepare message qubit (q0) with input_bit in chosen basis.
        Entangle with Alice's Bell pair half (q1).
        Perform Bell State Measurement (BSM) producing classical bits c0, c1.
        """
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(3, "c")
        qc = QuantumCircuit(qr, cr)

        # 1. State preparation on q0
        if input_bit == 1:
            qc.x(0)
        if basis == "X":
            qc.h(0)

        # 2. Shared Bell pair on (q1, q2)
        qc.h(1)
        qc.cx(1, 2)
        qc.barrier()

        # 3. Alice Bell State Measurement on (q0, q1)
        qc.cx(0, 1)
        qc.h(0)
        qc.barrier()

        qc.measure(0, 0)
        qc.measure(1, 1)

        counts = execute_circuit(qc, backend_type=self.backend_type, shots=1)
        res = list(counts.keys())[0].replace(" ", "")
        # Qiskit registers: c2 c1 c0
        c1 = int(res[-2])
        c0 = int(res[-1])

        return qc, c0, c1

    def teleport_single_qubit(
        self,
        input_bit: int,
        sender_basis: str = "Z",
        bob_basis: str = "Z",
        attack_type: Optional[str] = None,
        c0_flip: bool = False,
        c1_flip: bool = False,
    ) -> Dict[str, Any]:
        """
        Full round: Alice BSM -> 2-bit classical send -> Bob Pauli correction -> measurement.
        """
        qr = QuantumRegister(3, "q")
        cr = ClassicalRegister(3, "c")
        qc = QuantumCircuit(qr, cr)

        # 1. Message preparation on q0
        if input_bit == 1:
            qc.x(0)
        if sender_basis == "X":
            qc.h(0)

        # 2. Entangled Bell pair |Phi+> on (q1, q2)
        qc.h(1)
        qc.cx(1, 2)
        qc.barrier()

        # 3. Alice BSM
        qc.cx(0, 1)
        qc.h(0)
        qc.barrier()

        # Measure Alice qubits
        qc.measure(0, 0)
        qc.measure(1, 1)

        # 4. Bob's conditional Pauli correction on q2: Z^c0 X^c1
        # In Qiskit, deferred measurement representation applies corrections directly:
        qc.cx(1, 2)  # X correction if c1 == 1
        qc.cz(0, 2)  # Z correction if c0 == 1

        # Simulate classical channel tampering on c0/c1 if specified
        if c1_flip:
            qc.x(2)
        if c0_flip:
            qc.z(2)

        # Simulate quantum optical channel attacks on transmitted qubit q2
        if attack_type == "intercept_resend":
            qc.measure(2, 2)
        elif attack_type == "tampering":
            qc.x(2)
        elif attack_type == "disturbance":
            qc.rx(1.2, 2)

        # 5. Bob measurement in bob_basis
        if bob_basis == "X":
            qc.h(2)
        qc.measure(2, 2)

        counts = execute_circuit(qc, backend_type=self.backend_type, shots=1)
        res_str = list(counts.keys())[0].replace(" ", "")

        # Bits: c2 c1 c0
        bob_recovered_bit = int(res_str[0])
        c1 = int(res_str[1])
        c0 = int(res_str[2])

        is_success = (bob_recovered_bit == input_bit) if sender_basis == bob_basis else None

        return {
            "input_bit": input_bit,
            "sender_basis": sender_basis,
            "bob_basis": bob_basis,
            "classical_bits": (c0, c1),
            "bob_bit": bob_recovered_bit,
            "success": is_success,
        }
