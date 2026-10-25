from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
import os

def get_backend(backend_type='simulator', credentials=None):
    if backend_type == 'simulator':
        return AerSimulator()
        
    elif backend_type == 'noisy':
        # Simple depolarizing noise model calibrated for realistic channel baseline (Q0 = 1%)
        noise_model = NoiseModel()
        error = depolarizing_error(0.003, 1)  # 0.3% error per 1-qubit gate
        error2 = depolarizing_error(0.003, 2)  # 0.3% error per 2-qubit gate
        noise_model.add_all_qubit_quantum_error(error, ['u1', 'u2', 'u3', 'x', 'z', 'h'])
        noise_model.add_all_qubit_quantum_error(error2, ['cx', 'cz'])
        return AerSimulator(noise_model=noise_model)
        
    elif backend_type == 'hardware':
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            if credentials and 'token' in credentials:
                service = QiskitRuntimeService(channel="ibm_quantum", token=credentials['token'])
                return service.backend(credentials.get('backend_name', 'ibm_kyoto'))
            else:
                service = QiskitRuntimeService()
                return service.backend('ibm_kyoto')
        except ImportError:
            raise ImportError("Please install the hardware extra: pip install qusec[hardware]")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to IBM Quantum. Ensure credentials are valid.")
            
    return AerSimulator()

def execute_circuit(circuit, backend_type='simulator', backend=None, credentials=None, shots=1000):
    if backend is None:
        backend = get_backend(backend_type, credentials=credentials)
        
    result = backend.run(circuit, shots=shots).result()
    return result.get_counts()
