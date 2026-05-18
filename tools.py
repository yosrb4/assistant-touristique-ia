"""Tools : sélection intelligente des hôtels."""

from rag import filter_hotels, get_all_hotels_in_city, get_places
from agent_extract import PREMIUM_BUDGET

__all__ = ["get_places", "get_hotels", "resolve_hotels"]


def get_hotels(city: str, max_price: float) -> list[dict]:
    """
    Retourne une liste plate d'hôtels recommandés (principaux + alternatives).

    Args:
        city: Nom de la ville.
        max_price: Budget par nuit en DT.

    Returns:
        Liste combinée hotels + alternatives de resolve_hotels().
    """
    result = resolve_hotels(city, max_price)
    return result["hotels"] + result.get("alternatives", [])


def resolve_hotels(city: str, budget: float) -> dict:
    """
    Sélectionne les hôtels selon la ville et le budget (logique métier).

    Modes possibles :
    - premium : budget >= 200 DT → hôtels les plus chers
    - match : hôtels <= budget
    - alternatives : aucun dans le budget → propositions proches

    Args:
        city: Nom de la ville.
        budget: Budget par nuit en DT.

    Returns:
        Dict avec clés hotels, alternatives, mode, note.
    """
    in_budget = filter_hotels(city, budget)
    all_city = get_all_hotels_in_city(city)

    if budget >= PREMIUM_BUDGET and all_city:
        premium = sorted(all_city, key=lambda h: h["prix"], reverse=True)[:5]
        return {
            "hotels": premium,
            "alternatives": [],
            "mode": "premium",
            "note": f"Selection premium (budget {int(budget)} DT/nuit).",
        }

    if in_budget:
        return {"hotels": in_budget, "alternatives": [], "mode": "match", "note": None}

    if not all_city:
        return {
            "hotels": [],
            "alternatives": [],
            "mode": "alternatives",
            "note": f"Aucun hotel reference a {city}. Essayez Tunis ou Sousse.",
        }

    closest = sorted(all_city, key=lambda h: abs(h["prix"] - budget))[:3]
    cheapest = sorted(all_city, key=lambda h: h["prix"])[:2]
    seen, alts = set(), []
    for h in closest + cheapest:
        if h["nom"] not in seen:
            seen.add(h["nom"])
            alts.append(h)

    return {
        "hotels": [],
        "alternatives": alts[:4],
        "mode": "alternatives",
        "note": (
            f"Aucun hotel <= {int(budget)} DT. Plus proche : "
            f"{closest[0]['nom']} ({closest[0]['prix']} DT)."
        ),
    }
