import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse, parse_qs
from api.common import API, db

FIELDS = "apelido, origem, destino, max_preco_alerta, ativo, data_inicio, data_fim"

def validate(data):
    name = str(data.get("apelido", "")).strip()
    origin = str(data.get("origem", "")).strip().upper()
    destination = str(data.get("destino", "")).strip().upper()
    if not name or len(name) > 100:
        raise ValueError("Apelido obrigatório, com até 100 caracteres.")
    if not all(re.fullmatch(r"[A-Z]{3}", code) for code in (origin, destination)) or origin == destination:
        raise ValueError("Escolha códigos IATA distintos com três letras.")
    try:
        price = Decimal(str(data.get("max_preco_alerta", "")))
    except InvalidOperation:
        raise ValueError("Teto de preço inválido.")
    if not price.is_finite() or not Decimal("0") < price <= Decimal("9999999999.99") or price.as_tuple().exponent < -2:
        raise ValueError("Teto deve ser positivo e ter até duas casas decimais.")
    start, end = date.fromisoformat(data["data_inicio"]), date.fromisoformat(data["data_fim"])
    if not 0 <= (end-start).days <= 30:
        raise ValueError("Escolha um intervalo de até 31 dias.")
    active = data.get("ativo", True)
    if not isinstance(active, bool):
        raise ValueError("ativo deve ser booleano.")
    return name, origin, destination, price, active, start, end

class handler(API):
    def do_GET(self):
        def action():
            with db() as conn, conn.cursor() as cur:
                cur.execute("SELECT * FROM rotas_monitoradas ORDER BY id DESC")
                return cur.fetchall()
        self.dispatch(action)

    def do_POST(self):
        def action():
            values = validate(self.body())
            with db() as conn, conn.cursor() as cur:
                cur.execute(f"INSERT INTO rotas_monitoradas ({FIELDS}) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *", values)
                return cur.fetchone()
        self.dispatch(action)

    def do_PUT(self):
        def action():
            data = self.body()
            values = validate(data)
            with db() as conn, conn.cursor() as cur:
                cur.execute("UPDATE rotas_monitoradas SET apelido=%s, origem=%s, destino=%s, max_preco_alerta=%s, ativo=%s, data_inicio=%s, data_fim=%s WHERE id=%s RETURNING *", (*values, int(data["id"])))
                row = cur.fetchone()
                if not row:
                    raise ValueError("Rota não encontrada.")
                return row
        self.dispatch(action)

    def do_DELETE(self):
        def action():
            route_id = int(parse_qs(urlparse(self.path).query)["id"][0])
            with db() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM rotas_monitoradas WHERE id=%s RETURNING id", (route_id,))
                if not cur.fetchone():
                    raise ValueError("Rota não encontrada.")
            return {"ok": True}
        self.dispatch(action)
