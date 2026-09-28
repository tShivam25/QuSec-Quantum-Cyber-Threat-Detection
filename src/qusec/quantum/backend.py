from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
import os

def get_backend(backend_type='simulator', credentials=None):
    if backend_type == 'simulator':
        return AerSimulator()
        
    elif backend_type == 'noisy':
        # Simple depolarizing noise model
        noise_model = NoiseModel()
        error = depolarizing_error(0.01, 1) # 1% error
        error2 = depolarizing_error(0.01, 2)
        noise_model.add_all_qubit_quantum_error(error, ['u1', 'u2', 'u3', 'x', 'z', 'h'])
        noise_model.add_all_qubit_quantum_error(error2, ['cx', 'cz'])
        return AerSimulator(noise_model=noise_model)
        
    elif backend_type == 'hardware':
        # In a real environment we would use QiskitRuntimeService
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
            
            # Using credentials dict to initialize service securely without hardcoding
            if credentials and 'token' in credentials:
                service = QiskitRuntimeService(channel="ibm_quantum", token=credentials['token'])
                return service.backend(credentials.get('backend_name', 'ibm_kyoto'))
            else:
                # Fallback to saved account or env vars
                service = QiskitRuntimeService()
                return service.backend('ibm_kyoto')
        except ImportError:
            raise ImportError("Please install the hardware extra: pip install qusec[hardware]")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to IBM Quantum. Ensure credentials are valid.")
            
    return AerSimulator()

def execute_circuit(circuit, backend_type='simulator', backend=None, shots=1000):
    if backend is None:
        backend = get_backend(backend_type)
        
    result = backend.run(circuit, shots=shots).result()
    return result.get_counts()
