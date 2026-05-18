/**
 * Chat web v3.0 — interface utilisateur pour l'agent touristique multi-step.
 */

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("form");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const loaderEl = document.getElementById("loader");
const landingEl = document.getElementById("landing");
const appEl = document.getElementById("app");
const startBtn = document.getElementById("startBtn");

const VERSION = "3.0";

let sessionId = sessionStorage.getItem("agent_sid") || "web-" + Date.now();
sessionStorage.setItem("agent_sid", sessionId);

/** State local synchronisé avec le serveur (ville, budget, jours, préférence). */
let state = { city: null, budget: null, days: null, preference: null };

/**
 * Fusionne le state renvoyé par l'API dans le state local.
 * Ne remplace jamais par null (évite d'effacer des données connues).
 * @param {Object|null} fromServer - State depuis la réponse JSON
 */
function mergeState(fromServer) {
  if (!fromServer) return;
  if (fromServer.city) state.city = fromServer.city;
  if (fromServer.budget != null) state.budget = fromServer.budget;
  if (fromServer.days != null) state.days = fromServer.days;
  if (fromServer.preference) state.preference = fromServer.preference;
}

/**
 * Convertit le markdown/emoji de la réponse bot en HTML.
 * @param {string} raw - Texte brut de l'agent
 * @returns {string} HTML pour insertion dans le DOM
 */
function formatBotMessage(raw) {
  const parts = [];
  const lines = raw.split("\n");

  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;

    if (/^📍|^🏨|^📅|^💡/.test(t) || /^Résumé|^Hôtels|^Itinéraire|^Conseils/i.test(t)) {
      parts.push(`<h3 class="section-heading">${escapeHtml(t)}</h3>`);
      continue;
    }

    const day = t.match(/^Jour\s*(\d+)\s*:?/i);
    if (day) {
      parts.push(`<h3 class="day-heading">Jour ${day[1]}</h3>`);
      continue;
    }

    if (/^[-•*]\s+/.test(t)) {
      parts.push(`<li>${inlineFormat(escapeHtml(t.replace(/^[-•*]\s+/, "")))}</li>`);
      continue;
    }

    if (t.startsWith("- ")) {
      parts.push(`<li>${inlineFormat(escapeHtml(t.slice(2)))}</li>`);
      continue;
    }

    parts.push(`<p>${inlineFormat(escapeHtml(t))}</p>`);
  }

  return parts.join("");
}

/**
 * Échappe les caractères HTML pour éviter les injections XSS.
 * @param {string} t - Texte brut
 * @returns {string} Texte sécurisé pour innerHTML
 */
function escapeHtml(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

/**
 * Transforme **gras** en balises <strong>.
 * @param {string} html - Texte déjà échappé
 * @returns {string}
 */
function inlineFormat(html) {
  return html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

/**
 * Ajoute un message (utilisateur ou bot) dans le fil de chat.
 * @param {"user"|"bot"} role - Auteur du message
 * @param {string} text - Contenu du message
 * @param {string} [meta] - HTML optionnel (badges étape, compteurs)
 */
function appendMessage(role, text, meta) {
  const wrap = document.createElement("div");
  wrap.className = `message message--${role}`;

  const av = document.createElement("div");
  av.className = "message__avatar";
  av.textContent = role === "user" ? "Vous" : "🗺";

  const bubble = document.createElement("div");
  bubble.className = "message__bubble";

  if (role === "user") {
    bubble.textContent = text;
  } else {
    const content = document.createElement("div");
    content.className = "message__content";
    content.innerHTML = formatBotMessage(text);
    bubble.appendChild(content);
    if (meta) {
      const m = document.createElement("div");
      m.className = "message__meta";
      m.innerHTML = meta;
      bubble.appendChild(m);
    }
  }

  wrap.appendChild(av);
  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
}

/**
 * Active ou désactive l'état de chargement (spinner, input bloqué).
 * @param {boolean} on - true pendant l'appel API
 */
function setLoading(on) {
  loaderEl.classList.toggle("hidden", !on);
  sendBtn.disabled = on;
  inputEl.disabled = on;
}

/**
 * Construit les badges HTML pendant le dialogue multi-step.
 * @param {Object} data - Réponse API (step, total_steps, status)
 * @returns {string} HTML des meta-tags
 */
function buildProgressMeta(data) {
  if (data.status !== "need_info" || data.step == null) return "";
  const tags = [];
  tags.push(`Étape ${data.step}/${data.total_steps}`);
  if (state.city) tags.push(`📍 ${state.city}`);
  if (state.budget != null) tags.push(`💰 ${state.budget} DT`);
  if (state.preference) tags.push(`✨ ${state.preference}`);
  if (state.days != null) tags.push(`📅 ${state.days} j`);
  return tags.map((t) => `<span class="meta-tag">${t}</span>`).join("");
}

/**
 * Construit les badges HTML après une réponse finale complète.
 * @param {Object} data - Réponse API (places_count, hotels_count)
 * @returns {string} HTML des meta-tags
 */
function buildOkMeta(data) {
  const tags = [];
  if (data.places_count) tags.push(`🏛 ${data.places_count} lieux`);
  if (data.hotels_count) tags.push(`🏨 ${data.hotels_count} hôtels`);
  return tags.map((t) => `<span class="meta-tag">${t}</span>`).join("");
}

/** Envoi du formulaire : POST /api/chat puis affichage de la réponse. */
formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  appendMessage("user", text);
  inputEl.value = "";
  setLoading(true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, state, session_id: sessionId }),
    });
    const data = await res.json();

    if (data.version !== VERSION) {
      appendMessage(
        "bot",
        `Serveur v${data.version || "?"} detecte. Relancez : python server.py puis http://127.0.0.1:8081`
      );
      return;
    }

    mergeState(data.state);
    console.log("[state]", state, "step", data.step, "/", data.total_steps);

    const meta = data.status === "ok" ? buildOkMeta(data) : buildProgressMeta(data);
    appendMessage("bot", data.message, meta);
  } catch (err) {
    console.error(err);
    appendMessage("bot", "Erreur : lancez python server.py puis http://127.0.0.1:8081");
  } finally {
    setLoading(false);
    inputEl.focus();
  }
});

/** Affiche l'écran de chat après le clic sur « Commencer ». */
startBtn.addEventListener("click", () => {
  landingEl.classList.add("landing--hidden");
  appEl.classList.remove("app--hidden");
  inputEl.focus();
});

/** Pré-remplit l'input avec un exemple de requête complète. */
document.getElementById("welcome")?.addEventListener("click", () => {
  inputEl.value = "3 jours a Sousse petit budget culture";
  inputEl.focus();
});
