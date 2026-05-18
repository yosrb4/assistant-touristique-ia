"""
RAG : places_clean.json + data.json — filtrage ville, préférence, budget.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
PLACES_PATH = ROOT / "places_clean.json"
DATA_PATH = ROOT / "data.json"

_places_cache: dict | None = None
_data_cache: dict | None = None

MAX_PLACES = 5

TYPE_PRIORITY = {
    "historic": 0,
    "heritage": 1,
    "museum": 2,
    "attraction": 3,
    "nature": 4,
}

IMPORTANCE_HINTS = [
    "medina of", "medina", "museum", "national museum", "bardo",
    "carthage", "amphitheatre", "unesco", "great mosque of", "ribat",
]

# Score préférence par type / nom de lieu
PREFERENCE_BOOST = {
    "plage": {
        "types": {"nature", "attraction"},
        "names": ["beach", "sea", "coast", "port", "marina", "lake", "lac", "island", "plage"],
    },
    "culture": {
        "types": {"historic", "heritage", "museum"},
        "names": ["museum", "mosque", "medina", "archaeological", "roman", "amphitheatre", "heritage", "bardo"],
    },
    "détente": {
        "types": {"nature", "attraction"},
        "names": ["park", "garden", "jardin", "nature", "lake", "oasis"],
    },
}


def _normalize(text: str) -> str:
    """
    Normalise un texte pour comparaison (minuscules, sans accents).

    Args:
        text: Chaîne à normaliser (ville, nom de lieu…).

    Returns:
        Texte normalisé (ex. « kelibia » pour « Kélibia »).
    """
    replacements = {
        "é": "e", "è": "e", "ê": "e", "à": "a", "â": "a",
        "î": "i", "ô": "o", "ù": "u", "û": "u", "ç": "c",
    }
    s = text.lower().strip()
    for old, new in replacements.items():
        s = s.replace(old, new)
    return s


def _importance_score(name: str) -> int:
    """
    Calcule un score de notoriété touristique d'un lieu (plus bas = mieux).

    Favorise les noms contenant medina, museum, carthage, unesco, etc.
    Pénalise les noms trop courts (souvent trop génériques).

    Args:
        name: Nom du lieu tel que dans le dataset.

    Returns:
        Score entier (0 = très pertinent).
    """
    n = name.lower()
    score = 10
    for i, hint in enumerate(IMPORTANCE_HINTS):
        if hint in n:
            score = min(score, i)
    if len(name) < 12:
        score += 5
    return score


def _preference_score(place: dict, preference: str | None) -> int:
    """
    Score de correspondance entre un lieu et la préférence utilisateur.

    Args:
        place: Dict lieu avec clés name, type, city.
        preference: « plage », « culture », « détente » ou None.

    Returns:
        0 = correspondance forte, 6 = faible, 5 = pas de préférence.
    """
    if not preference or preference not in PREFERENCE_BOOST:
        return 5
    cfg = PREFERENCE_BOOST[preference]
    ptype = place.get("type", "")
    pname = place.get("name", "").lower()
    if ptype in cfg["types"]:
        return 0
    if any(h in pname for h in cfg["names"]):
        return 1
    return 6


def load_places() -> dict:
    """
    Charge places_clean.json en mémoire (cache au premier appel).

    Returns:
        Dict JSON complet avec clé « places ».
    """
    global _places_cache
    if _places_cache is None:
        with open(PLACES_PATH, encoding="utf-8") as f:
            _places_cache = json.load(f)
    return _places_cache


def load_data() -> dict:
    """
    Charge data.json (hôtels manuels) en mémoire (cache au premier appel).

    Returns:
        Dict JSON avec clé « hotels ».
    """
    global _data_cache
    if _data_cache is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _data_cache = json.load(f)
    return _data_cache


def get_known_cities() -> list[str]:
    """
    Liste toutes les villes présentes dans places_clean.json.

    Returns:
        Liste triée de noms de villes (exclut « unknown »).
    """
    data = load_places()
    return sorted({p["city"] for p in data["places"] if p["city"] != "unknown"})


def get_places(city: str, preference: str | None = None, limit: int = MAX_PLACES) -> list[dict]:
    """
    Retourne les lieux touristiques les plus pertinents pour une ville.

    Filtre par ville, trie par préférence, importance et type, puis limite
    le nombre de résultats (défaut : 5) pour le RAG / prompt LLM.

    Args:
        city: Nom de la ville cible.
        preference: « plage », « culture », « détente » ou None.
        limit: Nombre maximum de lieux à retourner.

    Returns:
        Liste de dicts {name, type, city}.
    """
    data = load_places()
    city_norm = _normalize(city)
    matches = [p for p in data["places"] if _normalize(p["city"]) == city_norm]

    matches.sort(
        key=lambda p: (
            _preference_score(p, preference),
            _importance_score(p["name"]),
            TYPE_PRIORITY.get(p["type"], 99),
            p["name"].lower(),
        )
    )
    return matches[:limit]


def get_all_hotels_in_city(city: str) -> list[dict]:
    """
    Retourne tous les hôtels référencés pour une ville, triés par prix.

    Args:
        city: Nom de la ville.

    Returns:
        Liste de dicts {nom, ville, prix}.
    """
    data = load_data()
    city_norm = _normalize(city)
    return sorted(
        [h for h in data["hotels"] if _normalize(h["ville"]) == city_norm],
        key=lambda h: h["prix"],
    )


def filter_hotels(city: str, max_price: float) -> list[dict]:
    """
    Filtre les hôtels d'une ville dont le prix est <= max_price.

    Args:
        city: Nom de la ville.
        max_price: Budget maximum par nuit en DT.

    Returns:
        Liste d'hôtels dans le budget.
    """
    return [h for h in get_all_hotels_in_city(city) if h["prix"] <= max_price]


def get_rag_context(city: str, max_price: float | None, preference: str | None = None) -> str:
    """
    Construit un bloc texte formaté pour injection dans un prompt LLM.

    Combine lieux filtrés (max 5) et hôtels dans le budget.

    Args:
        city: Nom de la ville.
        max_price: Budget hôtel max ou None.
        preference: Préférence de voyage ou None.

    Returns:
        Chaîne multi-lignes « === LIEUX === » + « === HOTELS === ».
    """
    places = get_places(city, preference)
    lines = ["=== LIEUX (dataset) ==="]
    for p in places:
        lines.append(f"- {p['name']} [{p['type']}]")
    lines.append("\n=== HOTELS ===")
    if max_price is not None:
        for h in filter_hotels(city, max_price):
            lines.append(f"- {h['nom']} : {h['prix']} DT/nuit")
    return "\n".join(lines)


filter_places = get_places  # Alias rétrocompatibilité
