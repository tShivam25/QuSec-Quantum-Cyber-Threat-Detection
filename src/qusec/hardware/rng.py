"""
RandomSource for QuSec.
Provides entropy from ESP32 hardware True Random Number Generator (TRNG)
with seamless, cryptographically secure OS fallback (secrets/os.urandom) when
operating in simulation or without physical hardware.
"""

import os
import secrets
import logging
from typing import Sequence, TypeVar, Optional, List
from qusec.hardware.esp32 import ESP32Device, ESP32Detector

T = TypeVar("T")
logger = logging.getLogger("qusec.hardware.rng")


class RandomSource:
    """
    Entropy provider for QuSec quantum state preparation, basis selection,
    and one-time-pad key generation.
    """

    def __init__(self, esp32_device: Optional[ESP32Device] = None, force_simulation: bool = False):
        self.esp32 = esp32_device
        self.force_simulation = force_simulation
        self._buffer = bytearray()

        if not self.force_simulation and self.esp32 is None:
            # Attempt auto-detection
            self.esp32 = ESP32Detector.find_esp32()

    @property
    def is_hardware(self) -> bool:
        """True if physical ESP32 TRNG is active and accessible."""
        return (
            not self.force_simulation
            and self.esp32 is not None
            and self.esp32.is_connected
        )

    @property
    def source_name(self) -> str:
        if self.is_hardware:
            return f"ESP32-TRNG ({self.esp32.port})" # type: ignore
        return "CSPRNG (System/secrets)"

    def get_random_bytes(self, n: int) -> bytes:
        """
        Fetch n random bytes. Tries ESP32 hardware TRNG first;
        falls back to cryptographically secure OS entropy if unavailable.
        """
        if n <= 0:
            return b""

        if self.is_hardware and self.esp32:
            try:
                hw_bytes = self.esp32.get_hardware_random_bytes(n)
                if hw_bytes and len(hw_bytes) == n:
                    return hw_bytes
            except Exception as e:
                logger.debug("ESP32 RNG read error, falling back to CSPRNG: %s", e)

        # Fallback to system cryptographic random bytes
        return os.urandom(n)

    def get_random_bits(self, n: int) -> List[int]:
        """
        Returns a list of n random bits (each 0 or 1).
        """
        if n <= 0:
            return []
        needed_bytes = (n + 7) // 8
        raw = self.get_random_bytes(needed_bytes)
        bits = []
        for byte in raw:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
                if len(bits) == n:
                    return bits
        return bits[:n]

    def choice(self, seq: Sequence[T]) -> T:
        """Cryptographically secure choice from a sequence."""
        if not seq:
            raise IndexError("Cannot choose from an empty sequence")
        idx = secrets.randbelow(len(seq))
        return seq[idx]

    def random_float(self) -> float:
        """Return a uniform random float in [0.0, 1.0)."""
        raw = self.get_random_bytes(7)
        int_val = int.from_bytes(raw, "big")
        return (int_val >> 3) * (2 ** -53)

    def randbelow(self, upper_bound: int) -> int:
        """Return random int in [0, upper_bound)."""
        return secrets.randbelow(upper_bound)
