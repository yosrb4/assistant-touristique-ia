"""
Serveur web — python server.py
Ouvrir http://127.0.0.1:8080
"""

import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from agent import VERSION, process

ROOT = Path(__file__).parent
PORT = 8081


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/version":
            self._json({"version": VERSION})
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n).decode("utf-8"))
        msg = (data.get("message") or "").strip()
        if not msg:
            self._json({"status": "error", "message": "Message vide"})
            return
        sid = (data.get("session_id") or "default").strip()
        result = process(msg, state=data.get("state"), session_id=sid)
        print(f"[API v{VERSION}] {sid} -> {result.get('status')} state={result.get('state')}")
        self._json(result)

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(args[0])


def main():
    print(f"\n=== Assistant Touristique v{VERSION} ===")
    print(f"    http://127.0.0.1:{PORT}")
    print("    Arretez les anciens serveurs (Ctrl+C) avant de tester\n")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
