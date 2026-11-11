import hmac
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL ausente")
    return psycopg2.connect(url, connect_timeout=10, cursor_factory=RealDictCursor)

def encode(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)

class API(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, default=encode, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def dispatch(self, action):
        secret = os.environ.get("ADMIN_TOKEN", "")
        if not secret:
            return self.reply(503, {"error": "Configure ADMIN_TOKEN no servidor."})
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + secret):
            return self.reply(401, {"error": "Token de acesso inválido."})
        try:
            result = action()
            self.reply(200, result)
        except (ValueError, KeyError, TypeError) as exc:
            self.reply(400, {"error": str(exc) or "Dados inválidos."})
        except Exception:
            logging.exception("Falha na API")
            self.reply(503, {"error": "Serviço indisponível. Verifique configuração e logs do servidor."})

    def body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length < 1 or length > 16384:
            raise ValueError("Corpo da requisição inválido (máximo 16 KB).")
        result = json.loads(self.rfile.read(length))
        if not isinstance(result, dict):
            raise ValueError("Envie um objeto JSON.")
        return result
