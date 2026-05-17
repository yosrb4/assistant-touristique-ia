"""
Extraction ville / budget / durée depuis les messages (sans dépendance circulaire).
"""

import re

from rag import get_known_cities

KNOWN_CITIES = get_known_cities()

BUDGET_KEYWORDS = {
    "petit budget": 70,
    "budget serre": 50,
    "budget serré": 50,
    "economique": 70,
    "économique": 70,
    "pas cher": 55,
    "moyen": 100,
    "grand budget": 250,
    "luxe": 250,
    "premium": 250,
}

CITY_ALIASES = {
    "tunis": "Tunis", "tuniss": "Tunis", "tunisia": "Tunis", "carthage": "Tunis",
    "sousse": "Sousse", "soussse": "Sousse", "souss": "Sousse", "sfax": "Sfax", "kairouan": "Kairouan",
    "beja": "Béja", "béja": "Béja", "mahdia": "Mahdia",
    "monastir": "Monastir", "hammamet": "Hammamet", "nabeul": "Nabeul",
    "bizerte": "Bizerte", "gabes": "Gabès", "gabès": "Gabès",
    "tozeur": "Tozeur", "djerba": "Djerba", "jerba": "Djerba",
    "el jem": "El Jem", "dougga": "Dougga", "sbeitla": "Sbeitla",
    "matmata": "Matmata", "tataouine": "Tataouine", "medenine": "Médenine",
    "médenine": "Médenine", "kef": "Le Kef", "kelibia": "Kélibia",
    "zaghouan": "Zaghouan",
}

PREMIUM_BUDGET = 200
SMALL_BUDGET = 80


def get_known_cities_list() -> list[str]:
    return KNOWN_CITIES


def extract_city(query: str) -> str | None:
    q = query.lower().strip()
    for alias, canonical in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q and canonical in KNOWN_CITIES:
            return canonical
    for city in KNOWN_CITIES:
        if city.lower() in q:
            return city
    # Message court = nom de ville seul (ex: "Sousse")
    if q in {c.lower() for c in KNOWN_CITIES}:
        for city in KNOWN_CITIES:
            if city.lower() == q:
                return city
    return None


def extract_duration(query: str) -> int | None:
    patterns = [
        r"(\d+)\s*jours?",
        r"(\d+)\s*jour\b",
        r"pendant\s*(\d+)",
        r"(\d+)\s*nuits?",
        r"change(?:r)?\s+(?:en\s+)?(\d+)\s*j",
    ]
    for pat in patterns:
        m = re.search(pat, query.lower())
        if m:
            return int(m.group(1))
    return None


def extract_budget(query: str) -> float | None:
    q = query.lower()
    for keyword, amount in sorted(BUDGET_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in q:
            return float(amount)
    # 100 dt, 100 dts, 100DT, 100 dinars
    m = re.search(r"(\d+)\s*(?:dts?|dinars?|tnd)\b", q, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"budget\s*(?:de\s*)?(\d+)", q)
    if m:
        return float(m.group(1))
    # Montant seul : "80", "80 dt", "80DT"
    stripped = q.strip()
    if re.fullmatch(r"\d+", stripped):
        return float(stripped)
    m = re.search(r"^(\d+)\s*dt$", stripped, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def is_premium_budget(budget: float) -> bool:
    return budget >= PREMIUM_BUDGET


def is_small_budget(budget: float) -> bool:
    return budget <= SMALL_BUDGET
