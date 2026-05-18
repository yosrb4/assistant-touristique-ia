"""
Extraction : ville, budget, durée, préférence (messages utilisateur).
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

# Alias ville (fautes courantes)
CITY_ALIASES = {
    "tunis": "Tunis", "tuniss": "Tunis", "tunisia": "Tunis", "carthage": "Tunis",
    "sousse": "Sousse", "soussse": "Sousse", "souss": "Sousse",
    "sfax": "Sfax", "sfx": "Sfax",
    "kairouan": "Kairouan", "kairouna": "Kairouan", "kairwan": "Kairouan",
    "beja": "Béja", "béja": "Béja",
    "mahdia": "Mahdia", "monastir": "Monastir", "hammamet": "Hammamet",
    "nabeul": "Nabeul", "bizerte": "Bizerte", "gabes": "Gabès", "gabès": "Gabès",
    "tozeur": "Tozeur", "djerba": "Djerba", "jerba": "Djerba",
    "el jem": "El Jem", "dougga": "Dougga", "sbeitla": "Sbeitla",
    "matmata": "Matmata", "tataouine": "Tataouine", "medenine": "Médenine",
    "médenine": "Médenine", "kef": "Le Kef", "kelibia": "Kélibia", "zaghouan": "Zaghouan",
}

PREFERENCE_KEYWORDS = {
    "plage": "plage",
    "plages": "plage",
    "mer": "plage",
    "bord de mer": "plage",
    "balnéaire": "plage",
    "culture": "culture",
    "culturel": "culture",
    "musée": "culture",
    "musee": "culture",
    "musées": "culture",
    "patrimoine": "culture",
    "historique": "culture",
    "détente": "détente",
    "detente": "détente",
    "relax": "détente",
    "repos": "détente",
    "calme": "détente",
}

PREMIUM_BUDGET = 200  # Seuil « grand budget » (DT/nuit)
SMALL_BUDGET = 80     # Seuil « petit budget » (DT/nuit)

VALID_PREFERENCES = {"plage", "culture", "détente"}


def extract_city(query: str) -> str | None:
    """
    Extrait le nom de ville depuis un message utilisateur.

    Cherche d'abord les alias (fautes courantes), puis les villes connues
    du dataset, puis un message constitué uniquement d'un nom de ville.

    Args:
        query: Texte saisi par l'utilisateur.

    Returns:
        Nom canonique de la ville (ex. « Sousse ») ou None si non trouvé.
    """
    q = query.lower().strip()
    for alias, canonical in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q and canonical in KNOWN_CITIES:
            return canonical
    for city in KNOWN_CITIES:
        if city.lower() in q:
            return city
    if q in {c.lower() for c in KNOWN_CITIES}:
        for city in KNOWN_CITIES:
            if city.lower() == q:
                return city
    return None


def extract_duration(query: str) -> int | None:
    """
    Extrait la durée du séjour en jours depuis un message.

    Reconnaît les formulations « 3 jours », « 2 nuits », « pendant 5 », etc.

    Args:
        query: Texte saisi par l'utilisateur.

    Returns:
        Nombre de jours ou None si non détecté.
    """
    patterns = [
        r"(\d+)\s*jours?",
        r"(\d+)\s*jour\b",
        r"pendant\s*(\d+)",
        r"(\d+)\s*nuits?",
        r"combien.*?(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, query.lower())
        if m:
            return int(m.group(1))
    return None


def extract_budget(query: str) -> float | None:
    """
    Extrait le budget hôtel par nuit (en DT) depuis un message.

    Priorité : mots-clés (petit budget, luxe…), puis montant + devise,
    puis « budget 150 », puis un nombre seul si le message n'est qu'un chiffre.

    Args:
        query: Texte saisi par l'utilisateur.

    Returns:
        Montant en dinars ou None si non détecté.
    """
    q = query.lower()
    for keyword, amount in sorted(BUDGET_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in q:
            return float(amount)
    m = re.search(r"(\d+)\s*(?:dts?|dinars?|tnd)\b", q, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"budget\s*(?:de\s*)?(\d+)", q)
    if m:
        return float(m.group(1))
    stripped = q.strip()
    if re.fullmatch(r"\d+", stripped):
        return float(stripped)
    return None


def extract_preference(query: str) -> str | None:
    """
    Extrait la préférence de voyage : plage, culture ou détente.

    Args:
        query: Texte saisi par l'utilisateur.

    Returns:
        « plage », « culture », « détente » ou None.
    """
    q = query.lower().strip()
    for keyword, pref in sorted(PREFERENCE_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in q:
            return pref
    if q in VALID_PREFERENCES:
        return q
    return None


def preference_label(pref: str | None) -> str:
    """
    Convertit une préférence interne en libellé affichable.

    Args:
        pref: Valeur « plage », « culture », « détente » ou None.

    Returns:
        Libellé capitalisé (ex. « Culture ») ou « — » si absent.
    """
    labels = {"plage": "Plage", "culture": "Culture", "détente": "Détente"}
    return labels.get(pref or "", pref or "—")
