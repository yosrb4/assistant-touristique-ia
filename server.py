"""
Serveur web HTTP — sert l'interface et l'API /api/chat.
Lancer : python server.py puis http://127.0.0.1:8081
"""

import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from agent import VERSION, process

ROOT = Path(__file__).parent
PORT = 8081


class Handler(SimpleHTTPRequestHandler):
    """Handler HTTP : fichiers statiques + API REST de l'agent."""

    def __init__(self, *args, **kwargs):
        """Initialise le handler avec le répertoire racine du projet."""
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        """
        Gère les requêtes GET.

        - /api/version → renvoie la version de l'agent
        - Autres chemins → fichiers statiques (index.html, CSS, JS)
        """
        if urlparse(self.path).path == "/api/version":
            self._json({"version": VERSION})
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        """
        Gère POST /api/chat : envoie un message à l'agent touristique.

        Corps JSON attendu : { message, state?, session_id? }
        """
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
        """
        Envoie une réponse HTTP 200 avec corps JSON UTF-8.

        Args:
            data: Dict sérialisable en JSON.
        """
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """Redirige les logs HTTP vers stdout (une ligne par requête)."""
        print(args[0])


def main():
    """Démarre le serveur HTTP sur 127.0.0.1:8081."""
    print(f"\n=== Assistant Touristique v{VERSION} ===")
    print(f"    http://127.0.0.1:{PORT}")
    print("    Arretez les anciens serveurs (Ctrl+C) avant de tester\n")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
