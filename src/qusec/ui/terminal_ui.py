"""
Terminal UI Dashboard for QuSec.
Renders the real-time operational monitor matching the exact specification:
┌ QuSec · Alice ─────────────── ● Fibre OK  ● ESP32 OK ┐
│ Session a91f · Key pool 4,820 bits · QBER 2.1%       │
├ Pipeline ────────────────────────────────────────────┤
│ Encode ✓  Entangle ✓  Test ✓  Teleport ▶  Correct ·  │
├ Log ─────────────────────────────────────────────────┤
│ 14:02:11 Bell pairs sent: 512 (64 test pairs)        │
│ 14:02:12 Fidelity 0.97, CHSH 2.71 → channel trusted  │
└──────────────────────────────────────────────────────┘
"""

import time
from typing import List, Dict, Any, Optional
from rich.text import Text
from rich.console import Console


class TerminalUIDashboard:
    """
    Renders live QuSec terminal dashboard with pipeline state,
    hardware status dots, session statistics, and event log.
    """

    def __init__(self, role: str = "Sender", width: int = 56):
        r = role.lower()
        if r in ("alice", "sender"):
            self.role = "Sender"
        else:
            self.role = "Receiver"
        self.width = max(56, width)
        self.session_id = "----"
        self.key_pool_bits = 0
        self.qber = 0.0
        self.fibre_ok = True
        self.esp32_ok = True
        self.is_simulation = False

        # Pipeline stages: state can be 'done', 'active', 'pending', 'error'
        self.pipeline = {
            "Encode": "done",
            "Entangle": "done",
            "Test": "done",
            "Teleport": "active",
            "Correct": "pending",
        }

        self.logs: List[str] = []
        self.max_logs = 5

    def set_session_info(self, session_id: str, key_pool_bits: int, qber: float):
        self.session_id = session_id
        self.key_pool_bits = key_pool_bits
        self.qber = qber

    def set_hardware_status(self, fibre_ok: bool, esp32_ok: bool, is_simulation: bool = False):
        self.fibre_ok = fibre_ok
        self.esp32_ok = esp32_ok
        self.is_simulation = is_simulation

    def set_pipeline_stage(self, stage: str, state: str):
        if stage in self.pipeline:
            self.pipeline[stage] = state

    def add_log(self, message: str):
        t_str = time.strftime("%H:%M:%S")
        self.logs.append(f"{t_str} {message}")
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def _render_stage_icon(self, state: str) -> Text:
        if state == "done":
            return Text("✓", style="bold green")
        elif state == "active":
            return Text("▶", style="bold cyan")
        elif state == "error":
            return Text("✖", style="bold red")
        else:  # pending
            return Text("·", style="dim")

    def _pad_line(self, inner: Text) -> Text:
        """Wrap inner Text in │ ... │ padded to exactly self.width."""
        inner_len = inner.cell_len
        pad_len = max(0, self.width - 2 - inner_len)
        line = Text()
        line.append("│ ", style="cyan")
        line.append_text(inner)
        line.append(" " * pad_len)
        line.append("│\n", style="cyan")
        return line

    def render(self) -> Text:
        """Construct the live dashboard formatted to match the exact design."""
        w = self.width
        fibre_color = "green" if self.fibre_ok else "red"
        esp_color = "green" if self.esp32_ok else ("yellow" if self.is_simulation else "red")
        fibre_label = "Fibre OK" if self.fibre_ok else "Fibre ERR"
        esp_label = "ESP32 OK" if self.esp32_ok else ("ESP32 SIM" if self.is_simulation else "ESP32 OFF")

        # Top border: ┌ QuSec · Alice ─────────────── ● Fibre OK  ● ESP32 OK ┐
        title_left = f" QuSec · {self.role} "
        status_right = f" ● {fibre_label}  ● {esp_label} "
        dash_len = max(2, w - 2 - len(title_left) - len(status_right))

        top = Text()
        top.append("┌", style="cyan")
        top.append(title_left, style="bold white")
        top.append("─" * dash_len, style="cyan")
        top.append(" ● ", style=f"bold {fibre_color}")
        top.append(f"{fibre_label}  ", style="bold white")
        top.append("● ", style=f"bold {esp_color}")
        top.append(f"{esp_label} ", style="bold white")
        top.append("┐\n", style="cyan")

        # Session line: │ Session a91f · Key pool 4,820 bits · QBER 2.1%       │
        qber_color = "green" if self.qber < 0.04 else ("yellow" if self.qber < 0.06 else "bold red")
        session_inner = Text()
        session_inner.append("Session ", style="bold")
        session_inner.append(f"{self.session_id}", style="bold cyan")
        session_inner.append(" · Key pool ", style="dim")
        session_inner.append(f"{self.key_pool_bits:,} bits", style="bold green")
        session_inner.append(" · QBER ", style="dim")
        session_inner.append(f"{self.qber * 100:.1f}%", style=qber_color)
        line_session = self._pad_line(session_inner)

        # Divider 1: ├ Pipeline ────────────────────────────────────────────┤
        pipe_dash = max(1, w - 2 - len(" Pipeline "))
        div_pipe = Text()
        div_pipe.append("├", style="cyan")
        div_pipe.append(" Pipeline ", style="bold yellow")
        div_pipe.append("─" * pipe_dash, style="cyan")
        div_pipe.append("┤\n", style="cyan")

        # Pipeline stages line: │ Encode ✓  Entangle ✓  Test ✓  Teleport ▶  Correct ·  │
        pipe_inner = Text()
        for i, (stage, state) in enumerate(self.pipeline.items()):
            pipe_inner.append(f"{stage} ")
            pipe_inner.append_text(self._render_stage_icon(state))
            if i < len(self.pipeline) - 1:
                pipe_inner.append("  ")
        line_pipe = self._pad_line(pipe_inner)

        # Divider 2: ├ Log ─────────────────────────────────────────────────┤
        log_dash = max(1, w - 2 - len(" Log "))
        div_log = Text()
        div_log.append("├", style="cyan")
        div_log.append(" Log ", style="bold yellow")
        div_log.append("─" * log_dash, style="cyan")
        div_log.append("┤\n", style="cyan")

        # Log lines
        log_lines = Text()
        display_logs = self.logs[-4:] if self.logs else ["Channel initialized. Session ready."]
        for l in display_logs:
            inner_log = Text()
            t_part = l[:8]
            rest = l[9:] if len(l) > 9 else l
            inner_log.append(f"{t_part} ", style="dim")
            if "channel trusted" in rest or "trusted" in rest:
                inner_log.append(rest, style="green")
            elif "aborted" in rest.lower() or "threat" in rest.lower() or "error" in rest.lower():
                inner_log.append(rest, style="bold red")
            elif "teleport" in rest.lower() or "bell pairs" in rest.lower():
                inner_log.append(rest, style="cyan")
            else:
                inner_log.append(rest, style="white")
            log_lines.append_text(self._pad_line(inner_log))

        # Bottom border: └──────────────────────────────────────────────────────┘
        bot = Text()
        bot.append("└", style="cyan")
        bot.append("─" * (w - 2), style="cyan")
        bot.append("┘\n", style="cyan")

        # Honest note on quantum security model
        note = Text("Honest note: Laptop-to-laptop quantum-secure. Browser-to-gateway hop is local plaintext.\n", style="dim italic")

        result = Text()
        result.append_text(top)
        result.append_text(line_session)
        result.append_text(div_pipe)
        result.append_text(line_pipe)
        result.append_text(div_log)
        result.append_text(log_lines)
        result.append_text(bot)
        result.append_text(note)
        return result
