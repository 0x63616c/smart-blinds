"""Loopback-only authenticated HTTP bridge for the seven-blind simulator."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

from .simulator import Simulation


def now_ms():
    return time.monotonic_ns() // 1_000_000


class SimulatorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token: str, port: int = 8765):
        if len(token) < 32 or any(c.isspace() for c in token):
            raise ValueError("token must contain at least 32 non-whitespace characters")
        self.token = token
        self.simulation = Simulation(now_ms())
        self.lock = threading.RLock()
        self.halt = threading.Event()
        super().__init__(("127.0.0.1", port), Handler)
        self.worker = threading.Thread(target=self._advance, daemon=True)
        self.worker.start()

    def _advance(self):
        while not self.halt.wait(0.01):
            with self.lock:
                self.simulation.tick(now_ms())

    def server_close(self):
        self.halt.set()
        self.worker.join(timeout=1)
        with self.lock:
            self.simulation.stop()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server: SimulatorServer

    def log_message(self, *_):
        pass  # Avoid request/credential logging; this is a local simulation fixture.

    def _reply(self, code: int, body: dict):
        data = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        expected = "Bearer " + self.server.token
        if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            self._reply(401, {"error": "authentication_required"})
            return False
        return True

    def do_GET(self):
        if not self._authorized():
            return
        if self.path != "/v1/state":
            self._reply(404, {"error": "not_found"})
            return
        with self.server.lock:
            state = self.server.simulation.state()
        self._reply(200, state)

    def do_POST(self):
        if not self._authorized():
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("invalid_request_size")
            self.connection.settimeout(2)
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("invalid_request")
            with self.server.lock:
                if self.path == "/v1/stop" and payload == {}:
                    self.server.simulation.stop()
                elif self.path == "/v1/move":
                    if set(payload) != {"target", "position", "align"}:
                        raise ValueError("invalid_fields")
                    target, position, align = payload["target"], payload["position"], payload["align"]
                    if type(position) not in (int, float) or type(align) is not bool:
                        raise ValueError("invalid_position_or_alignment")
                    if target != "room" and (target not in self.server.simulation.nodes or align):
                        raise ValueError("invalid_target")
                    self.server.simulation.move(position, device_id=None if target == "room" else target, align=align)
                else:
                    self._reply(404, {"error": "not_found"})
                    return
            self._reply(202, {"accepted": True})
        except (ValueError, KeyError, TypeError, TimeoutError) as exc:
            self._reply(409, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with SimulatorServer(args.token_file.read_text().strip(), args.port) as server:
        print(f"SIMULATION ONLY: http://127.0.0.1:{server.server_port}; seven virtual blinds, no hardware")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
