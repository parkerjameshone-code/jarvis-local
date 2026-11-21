import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _Handler(BaseHTTPRequestHandler):
    routes: dict = {}
    seen: list = []

    def log_message(self, *a):
        pass

    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        type(self).seen.append((self.command, self.path, body))
        route = type(self).routes.get((self.command, self.path))
        if route is None:
            self.send_response(404)
            self.end_headers()
            return
        data = route if isinstance(route, bytes) else (
            json.dumps(route).encode() if not isinstance(route, str) else route.encode())
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_DELETE = _reply


@pytest.fixture
def fake_ollama():
    """A local fake HTTP server standing in for Ollama. Never the real one."""
    handler = type("H", (_Handler,), {"routes": {}, "seen": []})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    handler.url = f"http://127.0.0.1:{srv.server_port}"
    yield handler
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def dead_url():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"
