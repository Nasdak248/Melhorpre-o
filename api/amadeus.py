import os
import time
from decimal import Decimal
import requests

class Amadeus:
    def __init__(self):
        environment = os.getenv("AMADEUS_ENV", "test")
        if environment not in ("test", "production"):
            raise ValueError("AMADEUS_ENV deve ser test ou production.")
        self.base = "https://api.amadeus.com" if environment == "production" else "https://test.api.amadeus.com"
        self.session = requests.Session()
        self.token = None
        self.expires = 0

    def get(self, path, params):
        if time.time() >= self.expires:
            result = self.session.post(self.base + "/v1/security/oauth2/token", data={
                "grant_type": "client_credentials", "client_id": os.environ["AMADEUS_CLIENT_ID"],
                "client_secret": os.environ["AMADEUS_CLIENT_SECRET"]}, timeout=30)
            result.raise_for_status()
            token = result.json()
            self.token = token["access_token"]
            self.expires = time.time() + int(token["expires_in"]) - 30
        for attempt in range(3):
            result = self.session.get(self.base + path, params=params,
                headers={"Authorization": "Bearer " + self.token}, timeout=30)
            if result.status_code != 429 or attempt == 2:
                break
            time.sleep(min(int(result.headers.get("Retry-After", "2")), 30))
        result.raise_for_status()
        return result.json().get("data", [])

    def cheapest(self, origin, destination, departure):
        offers = self.get("/v2/shopping/flight-offers", {
            "originLocationCode": origin, "destinationLocationCode": destination,
            "departureDate": departure.isoformat(), "adults": 1,
            "currencyCode": "BRL", "max": 50})
        prices = [Decimal(o["price"]["grandTotal"]) for o in offers if o["price"]["currency"] == "BRL"]
        return min(prices) if prices else None
