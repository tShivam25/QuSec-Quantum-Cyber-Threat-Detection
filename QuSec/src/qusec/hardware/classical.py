"""
ClassicalChannel Driver: ESP32 Wi-Fi & Serial Wireless Bridge for QuSec.
Transmits all classical coordination messages (handshake, SARG04 candidate pairs,
sifting basis announcements, 2-bit teleportation corrections, Cascade parities,
Wegman-Carter MAC authentication tokens, and ACKs).
"""

import os
import json
import time
import socket
import logging
from typing import Optional, Dict, Any, Tuple
from qusec.hardware.esp32 import ESP32Device, ESP32Detector

logger = logging.getLogger("qusec.hardware.classical")

DEFAULT_CLASSICAL_PORT = 9877


class ClassicalChannel:
    """
    Classical channel driver coordinating classical communication wirelessly
    via ESP32 Wi-Fi or local IP network fallback.
    """

    def __init__(
        self,
        local_port: int = DEFAULT_CLASSICAL_PORT,
        peer_host: str = "127.0.0.1",
        peer_port: int = DEFAULT_CLASSICAL_PORT,
        esp32_device: Optional[ESP32Device] = None,
        force_simulation: bool = False,
    ):
        self.local_port = local_port
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.esp32 = esp32_device
        self.force_simulation = force_simulation

        self._sock: Optional[socket.socket] = None
        self.is_open = False
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "last_latency_ms": 0.0,
        }

        self._auto_detect()

    def _auto_detect(self):
        """Auto-detect ESP32 microcontroller if available and not forced into simulation."""
        if not self.force_simulation and self.esp32 is None:
            self.esp32 = ESP32Detector.find_esp32()
            if self.esp32:
                logger.info("ClassicalChannel bound to ESP32: %s", self.esp32.port)

    @property
    def esp32_ok(self) -> bool:
        """True if ESP32 hardware bridge is connected, or ready in simulation."""
        if self.force_simulation:
            return True
        if self.esp32 and self.esp32.is_connected:
            return True
        # In software simulation mode, socket is ready
        return self.is_open

    def open(self) -> bool:
        """Initialize and bind classical socket."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._sock.settimeout(0.1)

            bind_ip = "0.0.0.0"
            self._sock.bind((bind_ip, self.local_port))
            self.is_open = True
            logger.info("ClassicalChannel bound to %s:%d (peer: %s:%d)", bind_ip, self.local_port, self.peer_host, self.peer_port)
            return True
        except Exception as e:
            logger.error("Failed to open ClassicalChannel on port %d: %s", self.local_port, e)
            self.is_open = False
            return False

    def close(self):
        """Close classical channel."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self.is_open = False
        if self.esp32:
            self.esp32.disconnect()

    def send_classical(self, msg_type: str, payload: Dict[str, Any], mac: Optional[str] = None) -> bool:
        """
        Send a classical message packet.
        If physical ESP32 is attached and configured for Wi-Fi transmission, forwards to ESP32;
        otherwise sends via direct UDP socket broadcast/unicast.
        """
        if not self.is_open or not self._sock:
            return False

        t0 = time.time()
        packet = {
            "channel": "classical_esp32",
            "type": msg_type,
            "ts": t0,
            "seq": self.stats["messages_sent"] + 1,
            "payload": payload,
            "mac": mac,
        }

        try:
            raw = json.dumps(packet).encode("utf-8")
            # If physical ESP32 has Wi-Fi TX firmware active, attempt forward:
            if self.esp32 and self.esp32.is_connected:
                self.esp32.send_classical_packet(raw)

            # Direct socket transmission to peer
            self._sock.sendto(raw, (self.peer_host, self.peer_port))
            self.stats["messages_sent"] += 1
            self.stats["bytes_sent"] += len(raw)
            return True
        except Exception as e:
            logger.error("Classical send error: %s", e)
            return False

    def receive_classical(self, timeout: float = 0.5) -> Optional[Dict[str, Any]]:
        """Receive a classical message packet."""
        if not self.is_open or not self._sock:
            return None

        self._sock.settimeout(timeout)
        try:
            data, addr = self._sock.recvfrom(65535)
            self.stats["messages_received"] += 1
            self.stats["bytes_received"] += len(data)
            packet = json.loads(data.decode("utf-8"))
            if "ts" in packet:
                self.stats["last_latency_ms"] = (time.time() - packet["ts"]) * 1000.0
            return packet
        except socket.timeout:
            return None
        except Exception as e:
            logger.debug("Classical receive exception: %s", e)
            return None

    def ping_esp32_link(self) -> Tuple[bool, float]:
        """Test responsiveness of the ESP32 classical bridge."""
        if self.esp32 and self.esp32.is_connected:
            t0 = time.perf_counter()
            ok = self.esp32.ping()
            dt_ms = (time.perf_counter() - t0) * 1000.0
            return ok, dt_ms
        return self.is_open, 0.1
