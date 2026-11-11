"""Servidor local de desenvolvimento; não usar em produção."""
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.rotas import handler as Routes
from api.historico import handler as History
from api.aeroportos import handler as Airports

class Dev(BaseHTTPRequestHandler):
    def route(self):
        path = urlparse(self.path).path
        api = {'/api/rotas': Routes, '/api/historico': History, '/api/aeroportos': Airports}.get(path)
        if api:
            method = getattr(api, 'do_' + self.command, None)
            if not method:
                return self.send_error(405)
            for name in ('reply', 'dispatch', 'body'):
                setattr(self, name, getattr(api, name).__get__(self))
            return method(self)
        if self.command != 'GET':
            return self.send_error(405)
        asset = {'/': ('index.html','text/html'), '/style.css': ('style.css','text/css'), '/app.js': ('app.js','text/javascript')}.get(path)
        if not asset:
            return self.send_error(404)
        body = (ROOT / 'public' / asset[0]).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', asset[1]+'; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)
    do_GET = do_POST = do_PUT = do_DELETE = route

if __name__ == '__main__':
    print('Flex: http://localhost:8000', flush=True)
    ThreadingHTTPServer(('127.0.0.1',8000),Dev).serve_forever()
