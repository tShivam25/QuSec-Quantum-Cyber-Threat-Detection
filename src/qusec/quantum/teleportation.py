import random
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qusec.quantum.backend import execute_circuit
from qusec.quantum.bell import correct

def create_teleportation_circuit(input_bit: int, sender_basis: str):
    """
    Creates the 3-qubit teleportation circuit for QuSec.
    q0: message
    q1: Alice Bell pair
    q2: Bob Bell pair
    """
    qr = QuantumRegister(3, 'q')
    cr = ClassicalRegister(3, 'c')
    qc = QuantumCircuit(qr, cr)

    # 1. Prepare q0
    if input_bit == 1:
        qc.x(0)
    if sender_basis == 'X':
        qc.h(0)

    # 2. Bell pair (q1, q2)
    qc.h(1)
    qc.cx(1, 2)
    qc.barrier()

    # 3. Teleportation sender ops
    qc.cx(0, 1)
    qc.h(0)
    qc.barrier()
    
    return qc

def simulate_round(input_bit: int, sender_basis: str, bob_basis: str, c0_flip=False, c1_flip=False,
                   attack_type=None, attack_prob=1.0, backend_type='simulator', credentials=None):
    """Run a full simulation of one bit using a single circuit with optional attack injection."""
    qc = create_teleportation_circuit(input_bit, sender_basis)
    
    # Dynamic corrections in deferred measurement form
    qc.cx(1, 2)
    qc.cz(0, 2)
    
    # Legacy classical flip logic
    if c1_flip:
        qc.x(2)
    if c0_flip:
        qc.z(2)

    # Attack simulation on transmitted state (qubit 2)
    if attack_type and random.random() < attack_prob:
        if attack_type == 'intercept_resend':
            # Eve measures in random basis (Z or X), collapsing state (Section VI-D)
            eve_basis = random.choice(['Z', 'X'])
            if eve_basis == 'X':
                qc.h(2)
            qc.measure(2, 2)
            if eve_basis == 'X':
                qc.h(2)
        elif attack_type == 'tampering':
            # Pauli channel tampering (Section III-E, VI-D)
            err = random.choice(['X', 'Y', 'Z'])
            if err == 'X': qc.x(2)
            elif err == 'Y': qc.y(2)
            elif err == 'Z': qc.z(2)
        elif attack_type == 'disturbance':
            # Unitary rotation Rx(theta)
            qc.rx(1.2, 2)
        elif attack_type == 'forgery':
            if random.random() < 0.5:
                qc.x(2)
            else:
                qc.h(2)
        elif attack_type == 'impersonation':
            qc.reset(2)
            if random.random() < 0.5:
                qc.x(2)
            if random.random() < 0.5:
                qc.h(2)
        elif attack_type == 'replay':
            if random.random() < 0.5:
                qc.h(2)
            if random.random() < 0.5:
                qc.x(2)
        elif attack_type == 'unauthorized_verification':
            qc.measure(2, 2)
        elif attack_type == 'custom':
            qc.rx(1.2, 2)
        
    if bob_basis == 'X':
        qc.h(2)
        
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    
    counts = execute_circuit(qc, backend_type=backend_type, credentials=credentials, shots=1)
    res_str = list(counts.keys())[0].replace(" ", "")
    
    # Qiskit returns bits as c2 c1 c0 from left to right
    bob_res = int(res_str[0])
    c1 = int(res_str[1])
    c0 = int(res_str[2])
    
    return c0, c1, bob_res, qc
