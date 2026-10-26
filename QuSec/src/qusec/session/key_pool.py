"""
Key Pool Manager for QuSec.
Maintains thread-safe shared secret key material, supports bit-level consumption
with cryptographic zeroization (burn-on-use), and triggers automated rekeying.
"""

import time
import threading
from typing import List, Dict, Any, Optional


class KeyPool:
    """
    Cryptographic Key Pool storing shared secret bits produced by SARG04
    entanglement distribution.
    """

    def __init__(self, rekey_threshold: int = 512, target_pool_size: int = 4096):
        self.rekey_threshold = rekey_threshold
        self.target_pool_size = target_pool_size
        self._bits: List[int] = []
        self._lock = threading.Lock()

        self.stats = {
            "total_generated_bits": 0,
            "total_consumed_bits": 0,
            "total_burned_bits": 0,
            "rekey_count": 0,
            "created_at": time.time(),
            "last_rekey_at": None,
        }

    @property
    def available_bits(self) -> int:
        """Current number of secret bits available in the pool."""
        with self._lock:
            return len(self._bits)

    def needs_rekey(self) -> bool:
        """True if key pool has depleted below rekey_threshold."""
        with self._lock:
            return len(self._bits) < self.rekey_threshold

    def add_keys(self, new_bits: List[int]):
        """Inject newly reconciled and amplified secret bits into the pool."""
        with self._lock:
            self._bits.extend(new_bits)
            self.stats["total_generated_bits"] += len(new_bits)
            self.stats["rekey_count"] += 1
            self.stats["last_rekey_at"] = time.time()

    def consume(self, num_bits: int) -> Optional[List[int]]:
        """
        Consume exactly num_bits from the pool for One-Time-Pad encryption.
        Zeroizes (burns) the consumed bits from memory immediately.
        """
        with self._lock:
            if len(self._bits) < num_bits:
                return None

            consumed = self._bits[:num_bits]
            # Overwrite in place before slicing (zeroization)
            for i in range(num_bits):
                self._bits[i] = 0

            self._bits = self._bits[num_bits:]
            self.stats["total_consumed_bits"] += num_bits
            self.stats["total_burned_bits"] += num_bits
            return consumed

    def burn_all(self):
        """Emergency zeroization of all key material in the pool."""
        with self._lock:
            for i in range(len(self._bits)):
                self._bits[i] = 0
            count = len(self._bits)
            self._bits.clear()
            self.stats["total_burned_bits"] += count

    def get_status(self) -> Dict[str, Any]:
        """Summary of current pool status."""
        with self._lock:
            avail = len(self._bits)
            return {
                "available_bits": avail,
                "available_bytes": avail // 8,
                "rekey_threshold": self.rekey_threshold,
                "target_pool_size": self.target_pool_size,
                "needs_rekey": avail < self.rekey_threshold,
                "total_generated": self.stats["total_generated_bits"],
                "total_consumed": self.stats["total_consumed_bits"],
                "total_burned": self.stats["total_burned_bits"],
                "rekey_count": self.stats["rekey_count"],
                "health": "OPTIMAL" if avail >= self.rekey_threshold else "REKEY_NEEDED",
            }
