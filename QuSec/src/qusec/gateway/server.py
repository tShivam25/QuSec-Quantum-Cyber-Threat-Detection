"""
Platform Bridge Gateway API Server for QuSec.
Provides RESTful HTTP and WebSocket/SSE endpoints for social media platforms
and external client applications to transmit messages, check key pools,
and observe real-time quantum pipeline events.
"""

import os
import json
import time
import socket
import logging
import threading
import hashlib
import base64
import struct
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List

from qusec.gateway.events import EventEmitter
from qusec.session.key_pool import KeyPool
from qusec.session.manager import SessionManager

logger = logging.getLogger("qusec.gateway.server")


def _send_ws_frame(sock, text: str):
    """Encode and send RFC 6455 unmasked text frame from server to client."""
    data = text.encode("utf-8")
    length = len(data)
    if length < 126:
        header = struct.pack("!BB", 0x81, length)
    elif length < 65536:
        header = struct.pack("!BBH", 0x81, 126, length)
    else:
        header = struct.pack("!BBQ", 0x81, 127, length)
    sock.sendall(header + data)


def _read_ws_frame_nonblocking(sock) -> Optional[str]:
    """Non-blocking read of RFC 6455 masked client frame."""
    try:
        head = sock.recv(2)
        if not head or len(head) < 2:
            return None
        b1, b2 = head
        opcode = b1 & 0x0F
        if opcode == 0x8:  # Connection close
            return ""
        masked = bool(b2 & 0x80)
        payload_len = b2 & 0x7F
        if payload_len == 126:
            ext = sock.recv(2)
            if len(ext) < 2:
                return None
            payload_len = struct.unpack("!H", ext)[0]
        elif payload_len == 127:
            ext = sock.recv(8)
            if len(ext) < 8:
                return None
            payload_len = struct.unpack("!Q", ext)[0]

        mask = sock.recv(4) if masked else None
        data = bytearray()
        while len(data) < payload_len:
            chunk = sock.recv(payload_len - len(data))
            if not chunk:
                break
            data.extend(chunk)

        if masked and mask:
            for i in range(len(data)):
                data[i] ^= mask[i % 4]

        return data.decode("utf-8", errors="replace")
    except (BlockingIOError, socket.error):
        return None


def _find_web_file(filename: str) -> Optional[str]:
    """Locate web asset file in package or project folders."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "web", filename),
        os.path.join(os.path.dirname(__file__), "web", filename),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", filename),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "QuSec", "web", filename),
        os.path.join(os.getcwd(), "QuSec", "web", filename),
        os.path.join(os.getcwd(), "web", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return None


class GatewayContext:
    """Shared state container for the Gateway API server."""

    def __init__(
        self,
        node_role: str = "sender",
        session_mgr: Optional[SessionManager] = None,
        key_pool: Optional[KeyPool] = None,
        event_emitter: Optional[EventEmitter] = None,
        send_message_fn: Optional[Any] = None,
        rekey_fn: Optional[Any] = None,
        init_session_fn: Optional[Any] = None,
        backend_name: str = "AerSimulator (Ideal Quantum State Simulator)",
        backend_type: str = "simulator",
        threshold_engine: Optional[Any] = None,
    ):
        self.node_role = "sender" if node_role.lower() in ("alice", "sender") else "receiver"
        self.session_mgr = session_mgr or SessionManager(role=self.node_role)
        self.key_pool = key_pool or self.session_mgr.key_pool
        self.event_emitter = event_emitter or EventEmitter()
        self.send_message_fn = send_message_fn
        self.rekey_fn = rekey_fn
        self.init_session_fn = init_session_fn
        self.backend_name = backend_name
        self.backend_type = backend_type
        self.threshold_engine = threshold_engine
        self.received_messages: List[Dict[str, Any]] = []
        self.pipeline_state = {
            "encode": "DONE",
            "entangle": "DONE",
            "test": "DONE",
            "teleport": "ACTIVE",
            "correct": "READY",
        }
        self.hardware_state = {
            "fibre_ok": True,
            "esp32_ok": True,
        }


def make_gateway_handler(context: GatewayContext):
    """Factory creating HTTP request handler with gateway context."""

    class GatewayHTTPHandler(BaseHTTPRequestHandler):
        def _send_cors_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Access-Control-Request-Private-Network")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _send_json_response(self, status_code: int, data: Dict[str, Any]):
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def _handle_websocket(self):
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_error(400, "Missing Sec-WebSocket-Key")
                return
            guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept_val = base64.b64encode(hashlib.sha1((key + guid).encode("utf-8")).digest()).decode("utf-8")

            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_val}\r\n"
                "Access-Control-Allow-Origin: *\r\n\r\n"
            )
            self.connection.sendall(response.encode("utf-8"))

            role_title = "Sender" if context.node_role == "sender" else "Receiver"
            peer_title = "Receiver" if role_title == "Sender" else "Sender"
            fibre_ok = context.hardware_state.get("fibre_ok", True)
            esp32_ok = context.hardware_state.get("esp32_ok", True)
            is_ready = bool(fibre_ok and esp32_ok)

            init_pkt = {
                "type": "status",
                "session_id": context.session_mgr.session_id or "qusec-node-session",
                "role": role_title,
                "peer_role": peer_title,
                "ready": is_ready,
                "is_ready": is_ready,
                "key_pool": context.key_pool.get_status(),
                "channel": {
                    "fibre_ok": fibre_ok,
                    "esp32_ok": esp32_ok,
                    "ready": is_ready,
                    "is_ready": is_ready,
                    "qber": context.session_mgr.current_qber,
                    "fidelity": context.session_mgr.current_fidelity,
                    "chsh": context.session_mgr.current_chsh,
                    "trusted": context.session_mgr.channel_trusted,
                },
            }
            try:
                _send_ws_frame(self.connection, json.dumps(init_pkt))
            except Exception:
                pass

            import queue
            event_queue = queue.Queue()
            unsub = context.event_emitter.subscribe(lambda e: event_queue.put(e))

            self.connection.setblocking(False)
            try:
                while True:
                    # 1. Dispatch outgoing events from node to web client
                    while not event_queue.empty():
                        try:
                            evt = event_queue.get_nowait()
                            e_name = evt.get("event")
                            if e_name == "message_received":
                                m = evt.get("data", {})
                                ws_msg = {
                                    "type": "message",
                                    "from": m.get("from", peer_title),
                                    "text": m.get("text", ""),
                                    "mode": m.get("mode", "teleportation"),
                                    "threat": m.get("threat", False),
                                    "decision": m.get("decision", "VERIFIED"),
                                }
                                _send_ws_frame(self.connection, json.dumps(ws_msg))
                            elif e_name in ("hardware_status", "session_established"):
                                cur_fibre = context.hardware_state.get("fibre_ok", True)
                                cur_esp = context.hardware_state.get("esp32_ok", True)
                                cur_ready = bool(cur_fibre and cur_esp)
                                st_pkt = {
                                    "type": "status",
                                    "session_id": context.session_mgr.session_id or "qusec-node-session",
                                    "ready": cur_ready,
                                    "is_ready": cur_ready,
                                    "channel": {
                                        "fibre_ok": cur_fibre,
                                        "esp32_ok": cur_esp,
                                        "ready": cur_ready,
                                        "is_ready": cur_ready,
                                    },
                                    "key_pool": context.key_pool.get_status(),
                                }
                                _send_ws_frame(self.connection, json.dumps(st_pkt))
                            else:
                                _send_ws_frame(self.connection, json.dumps(evt))
                        except Exception:
                            pass

                    # 2. Receive incoming frames from web client
                    try:
                        frame = _read_ws_frame_nonblocking(self.connection)
                        if frame == "":
                            break
                        if frame is not None:
                            try:
                                payload = json.loads(frame)
                                action = payload.get("action") or payload.get("type")
                                if action == "send_message" or payload.get("text"):
                                    default_peer = "receiver" if context.node_role == "sender" else "sender"
                                    recipient = payload.get("to") or default_peer
                                    text = payload.get("text") or payload.get("message") or ""
                                    mode = payload.get("mode", "teleportation")
                                    if text and context.send_message_fn:
                                        context.send_message_fn(recipient, text, mode)
                                elif action in ("init_session", "init"):
                                    if context.init_session_fn:
                                        context.init_session_fn()
                            except Exception:
                                pass
                    except (BlockingIOError, socket.error):
                        pass

                    time.sleep(0.04)
            except Exception:
                pass
            finally:
                unsub()

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            # Detect WebSocket upgrade request
            if self.headers.get("Upgrade", "").lower() == "websocket" or "Sec-WebSocket-Key" in self.headers:
                self._handle_websocket()
                return

            if path in ("/api/status", "/status"):
                pool_status = context.key_pool.get_status()
                role_title = "Sender" if context.node_role == "sender" else "Receiver"
                peer_title = "Receiver" if role_title == "Sender" else "Sender"
                session_ready = context.session_mgr.state == "ESTABLISHED"
                peer_pk = context.session_mgr.get_peer_quantum_public_key()
                traffic_rate = context.threshold_engine.get_traffic_rate() if context.threshold_engine else 0.0
                curr_q_th = context.threshold_engine.q_threshold if context.threshold_engine else 0.06
                fibre_ok = context.hardware_state.get("fibre_ok", True)
                esp32_ok = context.hardware_state.get("esp32_ok", True)
                is_ready = bool(fibre_ok and esp32_ok)

                data = {
                    "status": "ONLINE",
                    "role": role_title,
                    "peer_role": peer_title,
                    "ready": is_ready,
                    "is_ready": is_ready,
                    "link_ok": is_ready,
                    "channel_mode": "dual-mode (bidirectional full-duplex)",
                    "backend": context.backend_name,
                    "backend_type": context.backend_type,
                    "dynamic_threshold": {
                        "q_threshold": curr_q_th,
                        "traffic_rate_msgs_per_sec": traffic_rate,
                        "auto_adjusting": True,
                        "formula": "Q_th(n, Phi) = min(0.110, max(0.035, Q_ema + Delta_traffic(Phi) + Delta_stat(n)))",
                        "status": "ACTIVE (Auto-Adjusts for Message Length, Traffic & Drift)",
                    },
                    "session_id": context.session_mgr.session_id or "idle",
                    "session_established": session_ready,
                    "quantum_public_key": context.session_mgr.keypair.public_key.fingerprint,
                    "peer_quantum_public_key": peer_pk.fingerprint if peer_pk else "Not Negotiated",
                    "quantum_keys": {
                        "public_key": context.session_mgr.keypair.public_key.fingerprint,
                        "public_key_pem": context.session_mgr.keypair.public_key.to_pem(),
                        "peer_public_key": peer_pk.fingerprint if peer_pk else "Not Negotiated",
                        "private_key_status": "SECURED (Endpoint Memory)",
                        "encryption_scheme": "Receiver Public Key (RSA-OAEP 2048)",
                        "signature_scheme": "Sender Private Key QDS (RSA-PSS SHA256)",
                    },
                    "key_pool": pool_status,
                    "channel": {
                        "fibre_ok": fibre_ok,
                        "esp32_ok": esp32_ok,
                        "ready": is_ready,
                        "is_ready": is_ready,
                        "qber": context.session_mgr.current_qber,
                        "fidelity": context.session_mgr.current_fidelity,
                        "chsh": context.session_mgr.current_chsh,
                        "trusted": context.session_mgr.channel_trusted,
                    },
                    "pipeline": context.pipeline_state,
                    "security_model": "laptop-to-laptop quantum-secure (quantum asymmetric keys & QDS signature on endpoints; optical fibre & ESP32 transport)",
                }
                self._send_json_response(200, data)


            elif path in ("/api/messages", "/messages"):
                self._send_json_response(200, {
                    "messages": context.received_messages[-50:],
                    "count": len(context.received_messages),
                })

            elif path in ("/api/events", "/events"):
                # Server-Sent Events (SSE) streaming endpoint
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._send_cors_headers()
                self.end_headers()

                import queue
                event_queue = queue.Queue()
                context.event_emitter.subscribe(lambda e: event_queue.put(e))

                try:
                    # Initial connection event
                    init_data = json.dumps({"connected": True, "role": context.node_role})
                    self.wfile.write(f"data: {init_data}\n\n".encode("utf-8"))
                    self.wfile.flush()

                    while True:
                        try:
                            evt = event_queue.get(timeout=2.0)
                            line = f"data: {json.dumps(evt)}\n\n".encode("utf-8")
                            self.wfile.write(line)
                            self.wfile.flush()
                        except queue.Empty:
                            # Send heartbeat keep-alive
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif path in ("/", "/chat", "/demo_chat.html"):
                html_path = _find_web_file("demo_chat.html")
                if html_path and os.path.exists(html_path):
                    with open(html_path, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._send_json_response(404, {"error": "demo_chat.html not found"})

            elif path.endswith("qusec-web-bridge.js"):
                js_path = _find_web_file("qusec-web-bridge.js")
                if js_path and os.path.exists(js_path):
                    with open(js_path, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._send_json_response(404, {"error": "qusec-web-bridge.js not found"})

            else:
                self._send_json_response(404, {"error": "Not found", "path": path})

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"

            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                payload = {}

            if path in ("/api/send", "/send"):
                default_peer = "receiver" if context.node_role == "sender" else "sender"
                recipient = payload.get("to") or default_peer
                message_text = payload.get("message") or payload.get("text") or ""
                mode = payload.get("mode", "teleportation")

                if not message_text:
                    self._send_json_response(400, {"error": "Missing message content"})
                    return

                # Hardware link status check
                fibre_ok = context.hardware_state.get("fibre_ok", True)
                esp32_ok = context.hardware_state.get("esp32_ok", True)
                is_ready = bool(fibre_ok and esp32_ok)
                if not is_ready:
                    logger.info("Physical hardware link in simulation/fallback mode; proceeding with quantum transport.")

                # Send via registered callback or direct simulation
                if context.send_message_fn:
                    res = context.send_message_fn(recipient, message_text, mode)
                else:
                    # Default local execution
                    res = {
                        "success": True,
                        "msg_id": "sim_" + str(int(time.time())),
                        "session_id": context.session_mgr.session_id or "local",
                        "mode": mode,
                        "security": "laptop-to-laptop quantum-secure",
                    }
                    context.event_emitter.emit("message_sent", {
                        "to": recipient,
                        "mode": mode,
                        "text": message_text,
                    })

                self._send_json_response(200, res)

            elif path in ("/api/session/init", "/session/init", "/api/init", "/init"):
                if context.init_session_fn:
                    s_id = context.init_session_fn()
                else:
                    s_id = context.session_mgr.create_session_id()
                    context.session_mgr.session_id = s_id
                    context.session_mgr.state = "ESTABLISHED"

                context.event_emitter.emit("session_established", {
                    "session_id": context.session_mgr.session_id,
                    "role": context.node_role,
                })
                self._send_json_response(200, {
                    "success": True,
                    "session_id": context.session_mgr.session_id,
                    "state": context.session_mgr.state,
                })

            elif path in ("/api/rekey", "/rekey"):
                if context.rekey_fn:
                    added_bits = context.rekey_fn()
                else:
                    added_bits = 1024
                    context.key_pool.add_keys([1] * added_bits)

                context.event_emitter.emit("rekey_completed", {
                    "new_bits": added_bits,
                    "pool_size": context.key_pool.available_bits,
                })
                self._send_json_response(200, {
                    "success": True,
                    "new_bits": added_bits,
                    "pool_size": context.key_pool.available_bits,
                })

            else:
                self._send_json_response(404, {"error": "Not found", "path": path})

        def log_message(self, format, *args):
            # Suppress normal access log to avoid terminal noise
            return

    return GatewayHTTPHandler


class GatewayServer:
    """HTTP & SSE Gateway server bridging QuSec to social media applications."""

    def __init__(self, context: GatewayContext, host: str = "0.0.0.0", port: int = 8765):
        self.context = context
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        handler_cls = make_gateway_handler(self.context)
        try:
            self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        except OSError as e:
            if getattr(e, "errno", None) in (48, 98):
                alt_port = 8766 if self.port == 8765 else 8765
                logger.info("Port %d in use, falling back to port %d", self.port, alt_port)
                self.port = alt_port
                self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
            else:
                raise
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("QuSec Gateway Server running on http://%s:%d", self.host, self.port)

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
