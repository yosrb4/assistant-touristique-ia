"""
Agent touristique multi-step (v3.0) — dialogue progressif puis réponse structurée.
"""

import os

from dotenv import load_dotenv
from groq import Groq

from agent_extract import (
    extract_budget,
    extract_city,
    extract_duration,
    extract_preference,
    preference_label,
)
from rag import get_places
from tools import resolve_hotels

load_dotenv()

VERSION = "3.0"

EMPTY_STATE = {
    "city": None,
    "budget": None,
    "days": None,
    "preference": None,
}

# Ordre strict des questions (multi-step)
STEP_ORDER = ["city", "budget", "preference", "days"]

QUESTIONS = {
    "city": "Pour quelle ville souhaitez-vous un séjour ?",
    "budget": "Quel budget par nuit pour l'hôtel ?",
    "preference": "Préférez-vous : **plage**, **culture** ou **détente** ?",
    "days": "Combien de jours ?",
}

GLOBAL_STATE: dict[str, dict] = {}


def _get_state(session_id: str) -> dict:
    """
    Récupère ou crée l'état de conversation pour une session.

    Args:
        session_id: Identifiant unique (web, terminal…).

    Returns:
        Dict state {city, budget, days, preference}.
    """
    if session_id not in GLOBAL_STATE:
        GLOBAL_STATE[session_id] = dict(EMPTY_STATE)
        print(f"[STATE] nouvelle session {session_id}")
    return GLOBAL_STATE[session_id]


def _merge_client(session_id: str, client: dict | None) -> None:
    """
    Fusionne le state envoyé par le client (navigateur) avec celui du serveur.

    Ne remplace que les champs non nuls pour éviter d'effacer des données.

    Args:
        session_id: Identifiant de session.
        client: State partiel depuis le frontend ou None.
    """
    if not client:
        return
    s = _get_state(session_id)
    if client.get("city"):
        s["city"] = client["city"]
    if client.get("budget") is not None:
        s["budget"] = float(client["budget"])
    if client.get("days") is not None:
        s["days"] = int(client["days"])
    if client.get("preference"):
        s["preference"] = client["preference"]


def _update_from_message(session_id: str, message: str) -> list[str]:
    """
    Extrait les infos du message et met à jour le state de la session.

    Args:
        session_id: Identifiant de session.
        message: Texte utilisateur.

    Returns:
        Liste des champs modifiés (ex. ['city', 'budget']).
    """
    s = _get_state(session_id)
    updated = []

    city = extract_city(message)
    if city and city != s.get("city"):
        s["city"] = city
        updated.append("city")

    budget = extract_budget(message)
    if budget is not None and budget != s.get("budget"):
        s["budget"] = budget
        updated.append("budget")

    pref = extract_preference(message)
    if pref and pref != s.get("preference"):
        s["preference"] = pref
        updated.append("preference")

    days = extract_duration(message)
    if days is not None and days != s.get("days"):
        s["days"] = days
        updated.append("days")

    return updated


def _missing_fields(s: dict) -> list[str]:
    """
    Liste les champs obligatoires encore manquants dans le state.

    Args:
        s: State de la session.

    Returns:
        Liste parmi 'city', 'budget', 'preference', 'days'.
    """
    missing = []
    if not s.get("city"):
        missing.append("city")
    if s.get("budget") is None:
        missing.append("budget")
    if not s.get("preference"):
        missing.append("preference")
    if s.get("days") is None:
        missing.append("days")
    return missing


def _next_question(s: dict) -> str:
    """
    Génère la prochaine question à poser (une seule, dans l'ordre STEP_ORDER).

    Préfixe éventuellement par un résumé des infos déjà connues (« Noté — … »).

    Args:
        s: State actuel de la session.

    Returns:
        Texte de la question ou chaîne vide si tout est complet.
    """
    for field in STEP_ORDER:
        if field in _missing_fields(s):
            q = QUESTIONS[field]
            known = _summary_known(s, exclude=field)
            if known:
                return f"{known}\n\n{q}"
            return q
    return ""


def _summary_known(s: dict, exclude: str | None = None) -> str:
    """
    Résume les informations déjà collectées (pour confirmation utilisateur).

    Args:
        s: State de la session.
        exclude: Champ à ne pas afficher (celui qu'on demande ensuite).

    Returns:
        Chaîne « Noté — Ville : … · Budget : … » ou vide.
    """
    parts = []
    if s.get("city") and exclude != "city":
        parts.append(f"Ville : {s['city']}")
    if s.get("budget") is not None and exclude != "budget":
        parts.append(f"Budget : {int(s['budget'])} DT/nuit")
    if s.get("preference") and exclude != "preference":
        parts.append(f"Préférence : {preference_label(s['preference'])}")
    if s.get("days") is not None and exclude != "days":
        parts.append(f"Durée : {s['days']} jours")
    if not parts:
        return ""
    return "Noté — " + " · ".join(parts)


def _is_complete(s: dict) -> bool:
    """
    Vérifie si toutes les informations obligatoires sont renseignées.

    Args:
        s: State de la session.

    Returns:
        True si ville, budget, préférence et jours sont définis.
    """
    return len(_missing_fields(s)) == 0


def build_prompt(s: dict, places: list, hotel_result: dict) -> str:
    """
    Construit le prompt envoyé à Groq pour la réponse finale structurée.

    Injecte lieux RAG, hôtels filtrés et format obligatoire (résumé, itinéraire…).

    Args:
        s: State complet {city, budget, days, preference}.
        places: Liste de lieux depuis get_places().
        hotel_result: Résultat de resolve_hotels().

    Returns:
        Prompt texte pour le LLM.
    """
    days = s["days"]
    pref = preference_label(s["preference"])
    place_names = [p["name"] for p in places]

    hotels_main = hotel_result.get("hotels", [])
    hotels_alt = hotel_result.get("alternatives", [])
    hotels_lines = "\n".join(f"- {h['nom']} : {h['prix']} DT/nuit" for h in hotels_main)
    if hotels_alt:
        hotels_lines += "\n" + "\n".join(
            f"- {h['nom']} : {h['prix']} DT (alternative)" for h in hotels_alt
        )
    if hotel_result.get("note"):
        hotels_lines += f"\nNote: {hotel_result['note']}"

    places_lines = "\n".join(f"- {p['name']} ({p['type']})" for p in places)

    return f"""Tu es un guide touristique expert en Tunisie. Genere UNIQUEMENT la reponse finale structuree.

PARAMETRES :
- Ville : {s['city']}
- Budget : {s['budget']} DT/nuit
- Preference : {pref}
- Duree : {days} jours

LIEUX AUTORISES (utilise UNIQUEMENT ceux-ci, noms exacts) :
{places_lines}

HOTELS AUTORISES :
{hotels_lines}

FORMAT OBLIGATOIRE (respecte les titres et emojis) :

📍 Résumé :
- Ville : {s['city']}
- Budget : {s['budget']} DT/nuit
- Préférence : {pref}

🏨 Hôtels recommandés :
(liste avec prix en DT)

📍 Lieux à visiter :
(3 a 5 lieux reels de la liste)

📅 Itinéraire :

Jour 1 :
(activites precises avec noms de lieux, horaires suggeres)

Jour 2 :
(activites differentes du jour 1)

(continuer jusqu a Jour {days})

💡 Conseils pratiques :
(2 a 3 conseils concrets : transport, billets, meilleur moment)

INTERDIT : "explorer la ville", "decouvrir la culture", "flaner", phrases vagues sans lieu nomme.
OBLIGATOIRE : citer ces lieux : {", ".join(place_names)}
"""


def call_llm(prompt: str) -> str:
    """
    Appelle l'API Groq (Llama) pour générer la réponse touristique.

    Args:
        prompt: Instructions et contexte RAG.

    Returns:
        Texte généré par le modèle.

    Raises:
        ValueError: Si GROQ_API_KEY est absente du fichier .env.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY manquante dans .env")

    client = Groq(api_key=api_key)
    r = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Guide touristique Tunisie. Reponses structurees en francais. "
                    "Lieux reels uniquement. Jamais de conseils generiques."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=2000,
    )
    return r.choices[0].message.content


def process(user_query: str, state: dict | None = None, session_id: str | None = None) -> dict:
    """
    Point d'entrée principal de l'agent : traite un message utilisateur.

    Flux :
    1. Fusionne state client + extraction du message
    2. Si incomplet → pose une question (status need_info)
    3. Si complet → RAG + hôtels + appel LLM (status ok)

    Args:
        user_query: Message de l'utilisateur.
        state: State optionnel envoyé par le frontend.
        session_id: Identifiant de session pour la mémoire.

    Returns:
        Dict API : version, session_id, state, status, message, step, missing…
    """
    sid = (session_id or "default").strip() or "default"

    _merge_client(sid, state)
    updated = _update_from_message(sid, user_query)
    s = dict(_get_state(sid))

    print(f"[STATE] {sid} -> {s} | updated={updated}")

    step_done = sum(1 for k in STEP_ORDER if k not in _missing_fields(s))

    out = {
        "version": VERSION,
        "session_id": sid,
        "state": s,
        "updated": updated,
        "step": step_done,
        "total_steps": len(STEP_ORDER),
        "missing": _missing_fields(s),
    }

    if not _is_complete(s):
        out["status"] = "need_info"
        out["message"] = _next_question(s)
        return out

    places = get_places(s["city"], s.get("preference"))
    if not places:
        out["status"] = "error"
        out["message"] = (
            f"Peu de lieux pour « {s['city']} ». Essayez Tunis, Sousse ou Sfax."
        )
        return out

    hotel_result = resolve_hotels(s["city"], s["budget"])
    answer = call_llm(build_prompt(s, places, hotel_result))

    out["status"] = "ok"
    out["message"] = answer
    out["places_count"] = len(places)
    out["hotels_count"] = len(hotel_result.get("hotels", [])) + len(
        hotel_result.get("alternatives", [])
    )
    return out
