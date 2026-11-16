"""Sirve la app web en http://localhost:8080 para probarla en la PC.

En Windows, http.server toma los tipos de archivo del registro y a veces sirve
los .js como text/plain, y el navegador se niega a cargarlos como módulos.
Ejecutar desde la carpeta movil/:  py herramientas/servir.py
"""

import functools
import http.server
from pathlib import Path

WWW = Path(__file__).resolve().parent.parent / "www"


class Manejador(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".webmanifest": "application/manifest+json",
        ".wav": "audio/wav",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    servidor = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 8080), functools.partial(Manejador, directory=str(WWW)))
    print("Despertador Pato en http://localhost:8080  (Ctrl+C para cortar)")
    servidor.serve_forever()
