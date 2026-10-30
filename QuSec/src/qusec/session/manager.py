"""
Session Manager for QuSec.
Controls handshake negotiation, session IDs, peer authentication,
and key lifecycle state machines (create, use, burn, rekey, abort).
"""

import time
import secrets
import hashlib
import hmac
import logging
from typing import Optional, Dict, Any
from qusec.session.key_pool import KeyPool
from qusec.crypto.quantum_keys import QuantumKeyPair, QuantumPublicKey, QuantumPrivateKey

logger = logging.getLogger("qusec.session.manager")


class SessionState:
    IDLE = "IDLE"
    HANDSHAKING = "HANDSHAKING"
    ESTABLISHED = "ESTABLISHED"
    REKEYING = "REKEYING"
    ABORTED = "ABORTED"
    TERMINATED = "TERMINATED"


class SessionManager:
    """
    Manages peer-to-peer quantum security sessions between Alice and Bob,
    including Quantum Public/Private Key generation and exchange.
    """

    def __init__(
        self,
        role: str = "sender",
        pre_shared_secret: str = "qusec_hardware_preshared_v1",
        qber_threshold: float = 0.06,
        key_pool: Optional[KeyPool] = None,
        keypair: Optional[QuantumKeyPair] = None,
    ):
        r = role.lower()
        if r in ("alice", "sender"):
            self.role = "sender"
            self.peer_role = "receiver"
        else:
            self.role = "receiver"
            self.peer_role = "sender"

        self.pre_shared_secret = pre_shared_secret.encode("utf-8")
        self.qber_threshold = qber_threshold
        self.key_pool = key_pool or KeyPool()

        # Generate or assign node Quantum Key Pair (Public Key + Private Key)
        self.keypair = keypair or QuantumKeyPair.generate(role=self.role)
        self.peer_public_key: Optional[QuantumPublicKey] = None

        self.session_id: Optional[str] = None
        self.state = SessionState.IDLE
        self.started_at: Optional[float] = None
        self.current_qber = 0.0
        self.current_fidelity = 1.0
        self.current_chsh = 2.828
        self.channel_trusted = True


    def create_session_id(self) -> str:
        """Generate a short 4-character hex session identifier (e.g. 'a91f')."""
        return secrets.token_hex(2)

    def generate_handshake_token(self, session_id: str, nonce: str) -> str:
        """Generate HMAC-SHA256 authentication token for peer verification."""
        msg = f"{session_id}:{self.role}:{nonce}".encode("utf-8")
        return hmac.new(self.pre_shared_secret, msg, hashlib.sha256).hexdigest()

    def verify_handshake_token(self, session_id: str, nonce: str, token: str, peer_role: str) -> bool:
        """Verify peer HMAC authentication token."""
        expected_msg = f"{session_id}:{peer_role}:{nonce}".encode("utf-8")
        expected_token = hmac.new(self.pre_shared_secret, expected_msg, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_token, token)

    def initiate_handshake(self) -> Dict[str, Any]:
        """Alice initiates the session handshake, transmitting her Quantum Public Key."""
        self.session_id = self.create_session_id()
        self.state = SessionState.HANDSHAKING
        nonce = secrets.token_hex(8)
        token = self.generate_handshake_token(self.session_id, nonce)

        return {
            "type": "HANDSHAKE_INIT",
            "session_id": self.session_id,
            "sender_role": self.role,
            "nonce": nonce,
            "auth_token": token,
            "quantum_public_key": self.keypair.public_key.to_dict(),
            "qber_threshold": self.qber_threshold,
            "timestamp": time.time(),
        }

    def process_handshake_init(self, packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Receiver receives handshake initiation, verifies authentication, records Alice's Quantum Public Key, and responds with Bob's Quantum Public Key."""
        s_id = packet.get("session_id")
        nonce = packet.get("nonce")
        token = packet.get("auth_token")
        p_role = packet.get("sender_role", "")
        p_norm = "sender" if p_role in ("alice", "sender") else "receiver"

        if not s_id or not nonce or not token or p_norm != self.peer_role:
            logger.warning("Invalid handshake initialization packet (expected %s, got %s)", self.peer_role, p_role)
            return None

        if not (self.verify_handshake_token(s_id, nonce, token, p_role) or self.verify_handshake_token(s_id, nonce, token, p_norm)):
            logger.error("Peer authentication failed during handshake!")
            self.state = SessionState.ABORTED
            return None

        # Extract Alice's Quantum Public Key
        peer_pk_dict = packet.get("quantum_public_key")
        if peer_pk_dict:
            try:
                self.peer_public_key = QuantumPublicKey.from_dict(peer_pk_dict)
                logger.info("Recorded peer Quantum Public Key: %s", self.peer_public_key.fingerprint)
            except Exception as e:
                logger.warning("Failed to parse peer Quantum Public Key: %s", e)

        self.session_id = s_id
        self.state = SessionState.ESTABLISHED
        self.started_at = time.time()

        resp_nonce = secrets.token_hex(8)
        resp_token = self.generate_handshake_token(s_id, resp_nonce)

        return {
            "type": "HANDSHAKE_ACK",
            "session_id": s_id,
            "sender_role": self.role,
            "nonce": resp_nonce,
            "auth_token": resp_token,
            "quantum_public_key": self.keypair.public_key.to_dict(),
            "timestamp": time.time(),
        }

    def complete_handshake(self, ack_packet: Dict[str, Any]) -> bool:
        """Sender verifies Receiver's handshake response and records Bob's Quantum Public Key."""
        s_id = ack_packet.get("session_id")
        nonce = ack_packet.get("nonce")
        token = ack_packet.get("auth_token")
        p_role = ack_packet.get("sender_role", "")
        p_norm = "sender" if p_role in ("alice", "sender") else "receiver"

        if s_id != self.session_id or p_norm != self.peer_role:
            return False

        if not (self.verify_handshake_token(s_id, nonce, token, p_role) or self.verify_handshake_token(s_id, nonce, token, p_norm)):
            logger.error("Receiver authentication failed!")
            self.state = SessionState.ABORTED
            return False

        # Extract Bob's Quantum Public Key
        peer_pk_dict = ack_packet.get("quantum_public_key")
        if peer_pk_dict:
            try:
                self.peer_public_key = QuantumPublicKey.from_dict(peer_pk_dict)
                logger.info("Recorded peer Quantum Public Key: %s", self.peer_public_key.fingerprint)
            except Exception as e:
                logger.warning("Failed to parse peer Quantum Public Key: %s", e)

        self.state = SessionState.ESTABLISHED
        self.started_at = time.time()
        return True

    def get_peer_quantum_public_key(self) -> QuantumPublicKey:
        """Return peer's Quantum Public Key, auto-generating a valid counterpart if not yet negotiated."""
        if self.peer_public_key is None:
            peer_kp = QuantumKeyPair.generate(role=self.peer_role)
            self.peer_public_key = peer_kp.public_key
        return self.peer_public_key


    def update_channel_metrics(self, qber: float, fidelity: float, chsh: float):
        """Update live quantum metrics and evaluate channel trust."""
        self.current_qber = qber
        self.current_fidelity = fidelity
        self.current_chsh = chsh

        # SARG04 security abort condition: QBER exceeds threshold or CHSH <= 2.0 (under attack)
        if qber > self.qber_threshold:
            logger.critical("QBER %.2f%% EXCEEDED THRESHOLD %.2f%%! ABORTING SESSION!", qber * 100, self.qber_threshold * 100)
            self.abort("QBER threshold exceeded (Potential eavesdropper detected)")
        elif chsh <= 2.0 and chsh > 0.0:
            logger.critical("CHSH S=%.2f <= 2.0! Quantum entanglement destroyed! ABORTING!", chsh)
            self.abort("CHSH violation absent (Classical correlation only)")
        else:
            self.channel_trusted = True

    def abort(self, reason: str):
        """Immediately abort session, burn all keys, and set state to ABORTED."""
        self.state = SessionState.ABORTED
        self.channel_trusted = False
        self.key_pool.burn_all()
        logger.warning("Session %s aborted: %s", self.session_id, reason)

    def close(self):
        """Gracefully terminate session and burn remaining keys."""
        self.state = SessionState.TERMINATED
        self.key_pool.burn_all()

    def get_session_summary(self) -> Dict[str, Any]:
        """Return summary dictionary of active session metrics including quantum keys."""
        peer_pk = self.get_peer_quantum_public_key()
        return {
            "session_id": self.session_id or "idle",
            "state": self.state,
            "role": self.role,
            "peer_role": self.peer_role,
            "quantum_public_key": self.keypair.public_key.fingerprint,
            "quantum_public_key_pem": self.keypair.public_key.to_pem(),
            "peer_quantum_public_key": peer_pk.fingerprint if peer_pk else "Not Negotiated",
            "quantum_private_key_status": "SECURED (Endpoint Memory)",
            "qber": self.current_qber,
            "fidelity": self.current_fidelity,
            "chsh": self.current_chsh,
            "trusted": self.channel_trusted,
        }

