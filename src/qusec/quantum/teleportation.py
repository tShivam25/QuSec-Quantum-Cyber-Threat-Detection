from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qusec.quantum.backend import execute_circuit

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

def simulate_round(input_bit: int, sender_basis: str, bob_basis: str, c0_flip=False, c1_flip=False, backend_type='simulator', credentials=None):
    """Run a full simulation of one bit using a single circuit."""
    qc = create_teleportation_circuit(input_bit, sender_basis)
    
    # We apply dynamic corrections using quantum controlled gates
    qc.cx(1, 2)
    qc.cz(0, 2)
    
    # c1_flip logic (Classical flip means Bob gets opposite instruction)
    # Applying X(2) exactly models this error
    if c1_flip:
        qc.x(2)
        
    # c0_flip logic
    if c0_flip:
        qc.z(2)
        
    if bob_basis == 'X':
        qc.h(2)
        
    # Now we measure everything
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    
    counts = execute_circuit(qc, backend_type=backend_type, shots=1)
    res_str = list(counts.keys())[0].replace(" ", "")
    
    # Qiskit returns bits as c2 c1 c0 from left to right
    bob_res = int(res_str[0])
    c1 = int(res_str[1])
    c0 = int(res_str[2])
    
    return c0, c1, bob_res, qc

