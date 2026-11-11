"""Execute da raiz: python -m scripts.buscador_alertas"""
import logging
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
from api.common import db
from api.amadeus import Amadeus

log = logging.getLogger(__name__)

def telegram(text):
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    # Não registra URL ou exceção HTTP, pois a URL do Telegram contém o token.
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text}, timeout=30)
        return response.status_code == 200 and response.json().get("ok") is True
    except (requests.RequestException, ValueError):
        return False

def run():
    required = ("DATABASE_URL", "AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Configure: " + ", ".join(missing))
    cooldown = float(os.getenv("ALERT_COOLDOWN_HOURS", "24"))
    max_days = int(os.getenv("MAX_SEARCH_DAYS", "31"))
    if cooldown < 0 or not 1 <= max_days <= 31:
        raise ValueError("Configuração de limite ou cooldown inválida.")
    provider = Amadeus()
    failures = 0
    # Lock de sessão: evita duas execuções simultâneas, inclusive fora do Actions.
    conn = db()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(82917461) AS locked")
            if not cur.fetchone()["locked"]:
                log.info("Outra busca já está executando.")
                return
            cur.execute("SELECT * FROM rotas_monitoradas WHERE ativo ORDER BY id")
            routes = cur.fetchall()
        for route in routes:
            try:
                start = max(route["data_inicio"], date.today())
                end = route["data_fim"]
                if start > end:
                    log.info("Rota %s com período encerrado.", route["id"])
                    continue
                if (end-start).days + 1 > max_days:
                    raise ValueError("Intervalo excede MAX_SEARCH_DAYS")
                offers = []
                for offset in range((end-start).days + 1):
                    departure = start + timedelta(days=offset)
                    price = provider.cheapest(route["origem"], route["destino"], departure)
                    if price is not None:
                        offers.append((price, departure))
                if not offers:
                    log.info("Rota %s sem ofertas retornadas.", route["id"])
                    continue
                price, departure = min(offers)
                checked = datetime.now(timezone.utc)
                with conn.cursor() as cur:
                    # Confere novamente antes de gravar: rota pode ter sido editada durante a busca.
                    cur.execute("SELECT * FROM rotas_monitoradas WHERE id=%s", (route["id"],))
                    current = cur.fetchone()
                    if current != route:
                        log.info("Rota %s alterada; resultado descartado.", route["id"])
                        continue
                    cur.execute("""INSERT INTO historico_precos
                        (rota_id, origem, destino, data_voo, preco, data_consulta)
                        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (route["id"], route["origem"], route["destino"], departure, price, checked))
                    history_id = cur.fetchone()["id"]
                    cur.execute("""SELECT id FROM historico_precos WHERE rota_id=%s
                        AND alerta_enviado_em > now() - %s * interval '1 hour' LIMIT 1""", (route["id"], cooldown))
                    recent_alert = cur.fetchone()
                    if price <= route["max_preco_alerta"] and not recent_alert:
                        local = checked.astimezone(ZoneInfo("America/Sao_Paulo"))
                        label = "[AMBIENTE DE TESTE] " if os.getenv("AMADEUS_ENV", "test") == "test" else ""
                        text = (f"{label}✈ {route['apelido']}\n{route['origem']} → {route['destino']}"
                            f"\nR$ {price:.2f} · ida · 1 adulto\nVoo: {departure:%d/%m/%Y}"
                            f"\nConsulta: {local:%d/%m/%Y %H:%M:%S} (Brasília)"
                            "\nTarifa sujeita a disponibilidade. Confira bagagem e regras antes de comprar.")
                        if telegram(text):
                            cur.execute("UPDATE historico_precos SET alerta_enviado_em=now() WHERE id=%s", (history_id,))
                        else:
                            failures += 1
                            log.error("Falha ao enviar Telegram para rota %s.", route["id"])
                log.info("Rota %s: R$ %s em %s", route["id"], price, departure)
            except Exception as exc:
                failures += 1
                # Sem mensagem de exceção: bibliotecas podem incluir URLs sensíveis.
                log.error("Falha na rota %s (%s).", route["id"], type(exc).__name__)
    finally:
        conn.close()
    if failures:
        raise RuntimeError(f"{failures} falha(s). Veja os logs de rotas.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
