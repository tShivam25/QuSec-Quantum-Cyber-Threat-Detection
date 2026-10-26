"""
Bell state generation, entanglement distribution, and Pauli corrections as described in:
'QuSec: Cyber Threat Detection in Quantum Communication Channel' (Section III-B, III-E, VII).
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

def bell_pair() -> QuantumCircuit:
    """
    Generate maximally entangled Bell pair |Phi+> = (|00> + |11>) / sqrt(2).
    Paper Section VII:
        qc = QuantumCircuit(2)
        qc.h(0); qc.cx(0, 1)
    """
    qc = QuantumCircuit(2, name="bell_pair")
    qc.h(0)
    qc.cx(0, 1)
    return qc

def correct(qc: QuantumCircuit, m1: int, m2: int, target_qubit: int = 2):
    """
    Apply Pauli correction Z^m1 X^m2 on Bob's qubit based on Bell measurement outcomes (m1, m2).
    Paper Section III-E & Table I:
        (m1=0, m2=0) -> I
        (m1=1, m2=0) -> Z
        (m1=0, m2=1) -> X
        (m1=1, m2=1) -> X, then Z (equivalent to Z^m1 X^m2)
    """
    if m2:
        qc.x(target_qubit)
    if m1:
        qc.z(target_qubit)

def create_bell_correlator_circuit(basis: str = 'Z') -> QuantumCircuit:
    """
    Creates a circuit to measure the Bell pair in basis P in {Z, X, Y}.
    Paper Eq. (6):
        <ZZ> = <XX> = 1, <YY> = -1 for |Phi+>.
    """
    qr = QuantumRegister(2, 'q')
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)
    
    # Generate |Phi+>
    qc.h(0)
    qc.cx(0, 1)
    qc.barrier()
    
    # Basis rotation before measurement
    if basis == 'X':
        qc.h(0)
        qc.h(1)
    elif basis == 'Y':
        qc.sdg(0)
        qc.h(0)
        qc.sdg(1)
        qc.h(1)
        
    qc.measure(0, 0)
    qc.measure(1, 1)
    return qc

def compute_pauli_correlator(counts: dict) -> float:
    """
    Calculates expectation value <P (x) P> = p+ - p- from measurement bitstring counts.
    Paper Section III-A & III-B:
        outcome same (00 or 11) -> eigenvalue +1
        outcome opposite (01 or 10) -> eigenvalue -1
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    val = 0
    for bitstr, cnt in counts.items():
        clean_bits = bitstr.replace(" ", "")
        b0 = int(clean_bits[-1])
        b1 = int(clean_bits[-2])
        parity = 1 if b0 == b1 else -1
        val += parity * cnt
    return val / total
