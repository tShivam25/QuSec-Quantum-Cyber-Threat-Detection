from rich.console import Console
from rich.panel import Panel
from rich.align import Align

def print_banner():
    console = Console()
    ascii_art = """[bold blue]
 ██████╗ ██╗   ██╗███████╗███████╗ ██████╗
██╔═══██╗██║   ██║██╔════╝██╔════╝██╔════╝
██║   ██║██║   ██║███████╗█████╗  ██║     
██║▄▄ ██║██║   ██║╚════██║██╔══╝  ██║     
╚██████╔╝╚██████╔╝███████║███████╗╚██████╗
 ╚══▀▀═╝  ╚═════╝ ╚══════╝╚══════╝ ╚═════╝[/bold blue]"""
    
    content = Align.center(ascii_art + "\n\n[bold cyan]Quantum Security Framework[/bold cyan]\n[white]Teleportation-QDS • SARG04 • Threat Detection[/white]")
    console.print(Panel(content, border_style="blue"))
