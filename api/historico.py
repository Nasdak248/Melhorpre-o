from urllib.parse import urlparse, parse_qs
from api.common import API, db

class handler(API):
    def do_GET(self):
        def action():
            query = parse_qs(urlparse(self.path).query)
            days = int(query.get("dias", [30])[0])
            if not 1 <= days <= 365:
                raise ValueError("dias deve estar entre 1 e 365.")
            destination = query.get("destino", [""])[0].upper()
            with db() as conn, conn.cursor() as cur:
                cur.execute("""SELECT h.*, r.apelido FROM historico_precos h
                    JOIN rotas_monitoradas r ON r.id=h.rota_id
                    WHERE h.data_consulta >= now() - %s * interval '1 day'
                    AND (%s = '' OR h.destino=%s)
                    ORDER BY h.data_consulta DESC LIMIT 10000""", (days, destination, destination))
                return {"items": list(reversed(cur.fetchall())), "limite": 10000}
        self.dispatch(action)
