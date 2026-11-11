from urllib.parse import urlparse, parse_qs
from api.common import API
from api.amadeus import Amadeus

class handler(API):
    def do_GET(self):
        def action():
            keyword = parse_qs(urlparse(self.path).query).get("q", [""])[0].strip()
            if not 2 <= len(keyword) <= 60:
                raise ValueError("Digite entre 2 e 60 caracteres.")
            rows = Amadeus().get("/v1/reference-data/locations", {
                "subType": "AIRPORT,CITY", "keyword": keyword, "page[limit]": 12})
            return [{"codigo": row["iataCode"], "nome": row["name"],
                "cidade": row.get("address", {}).get("cityName", "")} for row in rows if row.get("iataCode")]
        self.dispatch(action)
