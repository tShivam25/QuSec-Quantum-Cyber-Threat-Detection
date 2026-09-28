import argparse
import sys
from rich.console import Console

from qusec.ui.banner import print_banner
from qusec.ui.monitor import InteractiveSimulator
from qusec import __version__

console = Console()

def main():
    parser = argparse.ArgumentParser(description="QuSec - Quantum Security Framework")
    parser.add_argument("--version", action="version", version=f"QuSec v{__version__}", help="Print version information")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the interactive simulator")
    version_parser = subparsers.add_parser("version", help="Print version information")

    run_parser.add_argument("--backend", choices=["simulator", "noisy", "hardware"], help="Backend execution mode")
    run_parser.add_argument("--shots", type=int, default=1000, help="Number of shots for verification")
    run_parser.add_argument("--threshold", type=float, default=0.06, help="QBER threshold")
    run_parser.add_argument("--mu-probability", type=float, default=0.6, help="Probability of mu decoy state")
    run_parser.add_argument("--nu-probability", type=float, default=0.3, help="Probability of nu decoy state")
    run_parser.add_argument("--vac-probability", type=float, default=0.1, help="Probability of vacuum decoy state")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    run_parser.add_argument("--debug", action="store_true", help="Enable debug output")
    run_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.command == "version":
        print(f"QuSec v{__version__}")
        return 0

    if not args.command or args.command == "run":
        if getattr(args, 'json', False) is False:
            print_banner()
            
        simulator = InteractiveSimulator(
            backend_type=getattr(args, 'backend', None),
            shots=getattr(args, 'shots', 1000),
            threshold=getattr(args, 'threshold', 0.06),
            mu_prob=getattr(args, 'mu_probability', 0.6),
            nu_prob=getattr(args, 'nu_probability', 0.3),
            vac_prob=getattr(args, 'vac_probability', 0.1),
            verbose=getattr(args, 'verbose', False),
            debug=getattr(args, 'debug', False),
            json_output=getattr(args, 'json', False)
        )
        simulator.run()
        return 0

    parser.print_help()
    return 1

if __name__ == "__main__":
    sys.exit(main())
