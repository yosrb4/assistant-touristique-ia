"""
Gestion du RAG : places_clean.json (lieux) + data.json (hôtels).
Ne jamais envoyer tout le JSON au LLM — toujours filtrer.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
PLACES_PATH = ROOT / "places_clean.json"
DATA_PATH = ROOT / "data.json"

_places_cache: dict | None = None
_data_cache: dict | None = None

# Priorité pour sélectionner les 5 lieux les plus pertinents
TYPE_PRIORITY = {
    "historic": 0,
    "heritage": 1,
    "museum": 2,
    "attraction": 3,
    "nature": 4,
}

MAX_PLACES = 5

# Mots-clés qui signalent un lieu majeur (score plus bas = plus prioritaire)
IMPORTANCE_HINTS = [
    "medina of", "medina", "museum", "national museum", "bardo",
    "carthage", "amphitheatre", "amphitheater", "unesco",
    "great mosque of", "cathedral", "kasbah", "ribat",
    "archaeological", "roman", "punic",
]


def _importance_score(name: str) -> int:
    """Score de pertinence touristique (plus bas = mieux)."""
    n = name.lower()
    score = 10
    for i, hint in enumerate(IMPORTANCE_HINTS):
        if hint in n:
            score = min(score, i)
    # Pénaliser noms trop courts / génériques
    if len(name) < 12:
        score += 5
    return score


def _normalize(text: str) -> str:
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    }
    s = text.lower().strip()
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def load_places() -> dict:
    global _places_cache
    if _places_cache is None:
        with open(PLACES_PATH, encoding="utf-8") as f:
            _places_cache = json.load(f)
    return _places_cache


def load_data() -> dict:
    """Charge data.json (hôtels)."""
    global _data_cache
    if _data_cache is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _data_cache = json.load(f)
    return _data_cache


def get_known_cities() -> list[str]:
    """Liste des villes présentes dans places_clean.json."""
    data = load_places()
    cities = {p["city"] for p in data["places"] if p["city"] != "unknown"}
    return sorted(cities)


def get_places(city: str, limit: int = MAX_PLACES) -> list[dict]:
    """
    Retourne au maximum `limit` lieux pertinents pour une ville.
    Priorise : historic, heritage, museum, attraction, nature.
    """
    data = load_places()
    city_norm = _normalize(city)

    matches = [
        p for p in data["places"]
        if _normalize(p["city"]) == city_norm
    ]

    matches.sort(
        key=lambda p: (
            _importance_score(p["name"]),
            TYPE_PRIORITY.get(p["type"], 99),
            p["name"].lower(),
        )
    )

    return matches[:limit]


def get_all_hotels_in_city(city: str) -> list[dict]:
    """Tous les hôtels d'une ville, triés par prix."""
    data = load_data()
    city_norm = _normalize(city)
    results = [
        h for h in data["hotels"]
        if _normalize(h["ville"]) == city_norm
    ]
    return sorted(results, key=lambda h: h["prix"])


def filter_hotels(city: str, max_price: float) -> list[dict]:
    """Filtre les hôtels par ville et prix maximum."""
    return [h for h in get_all_hotels_in_city(city) if h["prix"] <= max_price]


def get_rag_context(city: str, max_price: float | None = None) -> str:
    """Bloc texte filtré pour le prompt LLM (lieux + hôtels uniquement)."""
    places = get_places(city)
    lines = ["=== LIEUX TOURISTIQUES (dataset) ==="]
    if places:
        for p in places:
            lines.append(f"- {p['name']} [{p['type']}]")
    else:
        lines.append(f"(Aucun lieu trouvé pour {city})")

    lines.append("\n=== HÔTELS ===")
    if max_price is not None:
        hotels = filter_hotels(city, max_price)
        if hotels:
            for h in hotels:
                lines.append(f"- {h['nom']} : {h['prix']} DT/nuit")
        else:
            lines.append(f"(Aucun hôtel <= {max_price} DT)")
    else:
        lines.append("(Budget non précisé)")

    return "\n".join(lines)


# Alias rétrocompatibilité
filter_places = get_places
