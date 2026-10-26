"""
Platform Bridge Gateway API Server for QuSec.
Provides RESTful HTTP and WebSocket/SSE endpoints for social media platforms
and external client applications to transmit messages, check key pools,
and observe real-time quantum pipeline events.
"""

import json
import time
import socket
import logging
import threading
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List

from qusec.gateway.events import EventEmitter
from qusec.session.key_pool import KeyPool
from qusec.session.manager import SessionManager

logger = logging.getLogger("qusec.gateway.server")


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
    ):
        self.node_role = "sender" if node_role.lower() in ("alice", "sender") else "receiver"
        self.session_mgr = session_mgr or SessionManager(role=self.node_role)
        self.key_pool = key_pool or self.session_mgr.key_pool
        self.event_emitter = event_emitter or EventEmitter()
        self.send_message_fn = send_message_fn
        self.rekey_fn = rekey_fn
        self.init_session_fn = init_session_fn
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
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

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

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/status":
                pool_status = context.key_pool.get_status()
                role_title = "Sender" if context.node_role == "sender" else "Receiver"
                peer_title = "Receiver" if role_title == "Sender" else "Sender"
                session_ready = context.session_mgr.state == "ESTABLISHED"
                data = {
                    "status": "ONLINE",
                    "role": role_title,
                    "peer_role": peer_title,
                    "session_id": context.session_mgr.session_id or "idle",
                    "session_established": session_ready,
                    "key_pool": pool_status,
                    "channel": {
                        "fibre_ok": context.hardware_state["fibre_ok"],
                        "esp32_ok": context.hardware_state["esp32_ok"],
                        "qber": context.session_mgr.current_qber,
                        "fidelity": context.session_mgr.current_fidelity,
                        "chsh": context.session_mgr.current_chsh,
                        "trusted": context.session_mgr.channel_trusted,
                    },
                    "pipeline": context.pipeline_state,
                    "security_model": "laptop-to-laptop quantum-secure (keys and encryption reside on laptop endpoints; browser-to-gateway hop is local plaintext)",
                }
                self._send_json_response(200, data)

            elif path == "/api/messages":
                self._send_json_response(200, {
                    "messages": context.received_messages[-50:],
                    "count": len(context.received_messages),
                })

            elif path == "/api/events":
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

            if path == "/api/send":
                default_peer = "receiver" if context.node_role == "sender" else "sender"
                recipient = payload.get("to") or default_peer
                message_text = payload.get("message") or payload.get("text") or ""
                mode = payload.get("mode", "teleportation")

                if not message_text:
                    self._send_json_response(400, {"error": "Missing message content"})
                    return

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

            elif path == "/api/session/init":
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

            elif path == "/api/rekey":
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
        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("QuSec Gateway Server running on http://%s:%d", self.host, self.port)

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
