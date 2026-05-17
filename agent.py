"""
Agent touristique — state global simple (v2.1)
"""

import os

from dotenv import load_dotenv
from groq import Groq

from agent_extract import extract_budget, extract_city, extract_duration
from rag import get_rag_context
from tools import get_places, resolve_hotels

load_dotenv()

VERSION = "2.1"

# State global par session — cree une seule fois, jamais remis a zero
GLOBAL_STATE: dict[str, dict] = {}


def _get_state(session_id: str) -> dict:
    if session_id not in GLOBAL_STATE:
        GLOBAL_STATE[session_id] = {"city": None, "budget": None, "days": None}
        print(f"[STATE] nouvelle session {session_id}")
    return GLOBAL_STATE[session_id]


def _merge_client(session_id: str, client: dict | None) -> None:
    """Cumule client + serveur (les deux sources, jamais effacer par null)."""
    if not client:
        return
    s = _get_state(session_id)
    if client.get("city"):
        s["city"] = client["city"]
    if client.get("budget") is not None:
        s["budget"] = float(client["budget"])
    if client.get("days") is not None:
        s["days"] = int(client["days"])


def _update_from_message(session_id: str, message: str) -> None:
    s = _get_state(session_id)
    city = extract_city(message)
    if city:
        s["city"] = city
    budget = extract_budget(message)
    if budget is not None:
        s["budget"] = budget
    days = extract_duration(message)
    if days is not None:
        s["days"] = days


def _is_complete(s: dict) -> bool:
    return bool(s["city"]) and s["budget"] is not None


def _next_question(s: dict) -> str:
    if not s["city"]:
        hint = f" (budget {int(s['budget'])} DT deja note)" if s["budget"] else ""
        return f"Pour quelle ville ? (Tunis, Sousse, Sfax…){hint}"
    if s["budget"] is None:
        return f"Budget par nuit pour {s['city']} ? (ex. 100 dt, petit budget)"
    return ""


def run_tools(city: str, budget: float) -> tuple[list, dict]:
    return get_places(city), resolve_hotels(city, budget)


def build_prompt(user_query: str, s: dict, places: list, hotel_result: dict) -> str:
    days = s["days"] or 3
    names = [p["name"] for p in places]
    places_txt = "\n".join(f"- {p['name']}" for p in places)
    hotels_txt = "\n".join(
        f"- {h['nom']} : {h['prix']} DT" for h in hotel_result.get("hotels", [])
    )
    return f"""Guide Tunisie. Demande: {user_query}
Ville: {s['city']} | {days} jours | Budget: {s['budget']} DT/nuit
Lieux: {places_txt}
Hotels: {hotels_txt}
Itineraire **Jour 1** **Jour 2** avec lieux: {", ".join(names)}
"""


def call_llm(prompt: str) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    r = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": "Guide Tunisie. Francais. Lieux precis."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1500,
    )
    return r.choices[0].message.content


def process(user_query: str, state: dict | None = None, session_id: str | None = None) -> dict:
    sid = (session_id or "default").strip() or "default"

    s = _get_state(sid)
    _merge_client(sid, state)
    print(f"[STATE] {sid} AVANT:", dict(s))

    _update_from_message(sid, user_query)
    s = _get_state(sid)
    print(f"[STATE] {sid} APRES:", dict(s))

    out = {"version": VERSION, "session_id": sid, "state": dict(s)}

    if not _is_complete(s):
        out["status"] = "need_info"
        out["message"] = _next_question(s)
        return out

    places, hotels = run_tools(s["city"], s["budget"])
    if not places:
        out["status"] = "error"
        out["message"] = f"Aucun lieu pour {s['city']}. Essayez Tunis ou Sousse."
        return out

    out["status"] = "ok"
    out["message"] = call_llm(build_prompt(user_query, s, places, hotels))
    out["places_count"] = len(places)
    return out
