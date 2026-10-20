"""Loopback authenticated read-only bridge. No default devices or motion route."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from .service import Pairing, PhysicalBridge


class PhysicalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token, bridge, port=8766):
        if type(token) is not str or len(token) < 32 or any(c.isspace() for c in token):
            raise ValueError("Invalid bridge token")
        self.token, self.bridge = token, bridge
        super().__init__(("127.0.0.1", port), Handler)

    def server_close(self):
        super().server_close()
        self.bridge.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, value):
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer "+self.server.token):
            self.reply(401, {"error": "authentication_required"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path != "/v2/state":
            self.reply(404, {"error": "not_found"})
            return
        self.reply(200, self.server.bridge.state())

    def do_POST(self):
        if self.authorized():
            self.reply(405, {"error": "read_only"})


def load_pairings(path):
    """Explicit pre-existing pairing files; no identity generation or commissioning."""
    data = json.loads(path.read_text())
    if type(data) is not dict or set(data) != {"bridge_id", "devices"} or type(data["devices"]) is not list:
        raise ValueError("Invalid pairing configuration")
    result = []
    for item in data["devices"]:
        if type(item) is not dict or set(item) != {"id", "name", "host", "port", "identity", "key_file", "boot"}:
            raise ValueError("Invalid paired device")
        key_path = Path(item["key_file"])
        if not key_path.is_absolute():
            key_path = path.parent/key_path
        if key_path.is_symlink() or not key_path.is_file() or key_path.stat().st_size != 32 or key_path.stat().st_mode & 0o077:
            raise ValueError("Key must be a private regular file")
        key = key_path.read_bytes()
        boot = item["boot"]
        if type(boot) is not str or len(boot) != 16 or any(c not in "0123456789abcdef" for c in boot):
            raise ValueError("Expected boot must be exact lower-case hex")
        result.append(Pairing(item["id"], item["name"], item["host"], item["port"], item["identity"], key, int(boot, 16)))
    return data["bridge_id"], result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairings", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    bridge_id, pairings = load_pairings(args.pairings)
    bridge = PhysicalBridge(bridge_id, pairings, args.library)
    try:
        with PhysicalServer(args.token_file.read_text().strip(), bridge, args.port) as server:
            server.serve_forever()
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
