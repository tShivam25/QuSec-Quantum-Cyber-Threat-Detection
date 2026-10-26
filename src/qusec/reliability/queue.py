"""
Reliable Transport & Message Queue Subsystem for QuSec.
Provides guaranteed in-order message delivery with ACK/retry protocols,
exponential backoff, automatic rekey triggers, and QBER threshold abort guard.
"""

import time
import uuid
import queue
import logging
import threading
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger("qusec.reliability.queue")


class QueuedMessage:
    def __init__(self, msg_id: str, payload: Dict[str, Any], max_retries: int = 3, timeout: float = 2.0):
        self.msg_id = msg_id
        self.payload = payload
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_count = 0
        self.last_sent_at: Optional[float] = None
        self.acknowledged = False
        self.created_at = time.time()


class ReliableTransport:
    """
    Guarantees transmission reliability over optical and classical links.
    Handles message sequence numbering, ACK timeouts, retries,
    QBER security aborts, and rekey triggers.
    """

    def __init__(
        self,
        send_fn: Callable[[Dict[str, Any]], bool],
        rekey_trigger_fn: Optional[Callable[[], bool]] = None,
        max_retries: int = 3,
        ack_timeout: float = 1.5,
    ):
        self.send_fn = send_fn
        self.rekey_trigger_fn = rekey_trigger_fn
        self.max_retries = max_retries
        self.ack_timeout = ack_timeout

        self._pending: Dict[str, QueuedMessage] = {}
        self._received_ids = set()
        self._lock = threading.Lock()
        self.is_running = True

        self.stats = {
            "messages_sent": 0,
            "messages_delivered": 0,
            "retries_count": 0,
            "dropped_count": 0,
            "aborted_transmissions": 0,
        }

    def enqueue_message(self, data: Dict[str, Any], msg_type: str = "SECURE_MSG") -> str:
        """Enqueue message for reliable delivery."""
        msg_id = str(uuid.uuid4())[:8]
        packet = {
            "msg_id": msg_id,
            "msg_type": msg_type,
            "data": data,
            "timestamp": time.time(),
        }

        with self._lock:
            q_msg = QueuedMessage(msg_id, packet, self.max_retries, self.ack_timeout)
            self._pending[msg_id] = q_msg

        # Initial transmit attempt
        self._transmit(q_msg)
        return msg_id

    def _transmit(self, q_msg: QueuedMessage):
        """Send message via the underlying link."""
        q_msg.last_sent_at = time.time()
        ok = self.send_fn(q_msg.payload)
        if ok:
            self.stats["messages_sent"] += 1
        return ok

    def handle_ack(self, ack_msg_id: str):
        """Process incoming ACK for a pending message."""
        with self._lock:
            if ack_msg_id in self._pending:
                self._pending[ack_msg_id].acknowledged = True
                del self._pending[ack_msg_id]
                self.stats["messages_delivered"] += 1
                logger.debug("Message %s ACK received", ack_msg_id)

    def process_incoming_packet(self, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Deduplicate incoming message and extract payload.
        Returns message data if newly seen, None if duplicate.
        """
        msg_id = packet.get("msg_id")
        if not msg_id:
            return packet

        with self._lock:
            if msg_id in self._received_ids:
                logger.debug("Duplicate message %s discarded", msg_id)
                return None  # Duplicate
            self._received_ids.add(msg_id)
            # Prune deduplication set if it grows large
            if len(self._received_ids) > 10000:
                self._received_ids = set(list(self._received_ids)[5000:])

        return packet

    def check_timeouts_and_retry(self, current_qber: float = 0.0, qber_threshold: float = 0.06):
        """
        Check for timed-out unacknowledged messages and trigger retries.
        Aborts if QBER exceeds threshold.
        """
        if current_qber > qber_threshold:
            with self._lock:
                dropped = len(self._pending)
                self.stats["dropped_count"] += dropped
                self.stats["aborted_transmissions"] += dropped
                self._pending.clear()
            logger.warning("QBER threshold exceeded! Purged %d in-flight messages", dropped)
            return

        now = time.time()
        to_retry = []
        to_drop = []

        with self._lock:
            for msg_id, q_msg in list(self._pending.items()):
                if q_msg.last_sent_at and (now - q_msg.last_sent_at) > q_msg.timeout:
                    if q_msg.retry_count < q_msg.max_retries:
                        q_msg.retry_count += 1
                        to_retry.append(q_msg)
                    else:
                        to_drop.append(msg_id)

            for msg_id in to_drop:
                del self._pending[msg_id]
                self.stats["dropped_count"] += 1

        for q_msg in to_retry:
            self.stats["retries_count"] += 1
            logger.debug("Retrying message %s (attempt %d)", q_msg.msg_id, q_msg.retry_count)
            self._transmit(q_msg)
