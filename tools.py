"""
Fonctions outils (tools) pour l'agent touristique.
"""

from rag import filter_hotels, get_all_hotels_in_city, get_places
from agent_extract import PREMIUM_BUDGET

__all__ = ["get_places", "get_hotels", "resolve_hotels"]


def get_hotels(city: str, max_price: float) -> list[dict]:
    """Hôtels dans le budget (liste simple, rétrocompatibilité)."""
    result = resolve_hotels(city, max_price)
    return result["hotels"] + result.get("alternatives", [])


def resolve_hotels(city: str, budget: float) -> dict:
    """
    Résout les hôtels selon le budget avec alternatives et mode premium.

    Returns:
        {
          "hotels": [...],           # sélection principale
          "alternatives": [...],     # si aucun dans le budget
          "mode": "match|premium|alternatives",
          "note": str | None,
        }
    """
    in_budget = filter_hotels(city, budget)
    all_city = get_all_hotels_in_city(city)

    # Budget élevé → hôtels premium (les plus chers de la ville)
    if budget >= PREMIUM_BUDGET and all_city:
        premium = sorted(all_city, key=lambda h: h["prix"], reverse=True)[:5]
        return {
            "hotels": premium,
            "alternatives": [],
            "mode": "premium",
            "note": (
                f"Budget confortable ({int(budget)} DT/nuit) : "
                "sélection d'hôtels premium disponibles."
            ),
        }

    if in_budget:
        return {
            "hotels": in_budget,
            "alternatives": [],
            "mode": "match",
            "note": None,
        }

    # Aucun dans le budget → proposer alternatives (jamais « rien trouvé » seul)
    if not all_city:
        nearby_note = (
            f"Aucun hôtel référencé à {city} dans notre base. "
            "Envisagez Tunis ou Sousse (plus d'options) ou un hébergement en ligne."
        )
        return {
            "hotels": [],
            "alternatives": [],
            "mode": "alternatives",
            "note": nearby_note,
        }

    by_price = sorted(all_city, key=lambda h: h["prix"])
    closest = sorted(all_city, key=lambda h: abs(h["prix"] - budget))[:3]
    cheapest = by_price[:2]
    seen = set()
    alternatives = []
    for h in closest + cheapest:
        key = h["nom"]
        if key not in seen:
            seen.add(key)
            alternatives.append(h)

    cheapest_price = by_price[0]["prix"]
    note = (
        f"Aucun hôtel ≤ {int(budget)} DT/nuit à {city}. "
        f"Alternative la plus proche : {closest[0]['nom']} ({closest[0]['prix']} DT). "
        f"Option économique : {cheapest[0]['nom']} ({cheapest_price} DT)."
    )
    return {
        "hotels": [],
        "alternatives": alternatives[:4],
        "mode": "alternatives",
        "note": note,
    }
