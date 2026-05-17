/**
 * Chat web v2.1 — state synchronise avec le serveur
 */

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("form");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const loaderEl = document.getElementById("loader");
const landingEl = document.getElementById("landing");
const appEl = document.getElementById("app");
const startBtn = document.getElementById("startBtn");

// Session unique par onglet
let sessionId =
  sessionStorage.getItem("agent_sid") || "web-" + Date.now();
sessionStorage.setItem("agent_sid", sessionId);

// State local — ne jamais ecraser avec null
let state = { city: null, budget: null, days: null };

function mergeState(fromServer) {
  if (!fromServer) return;
  if (fromServer.city) state.city = fromServer.city;
  if (fromServer.budget != null) state.budget = fromServer.budget;
  if (fromServer.days != null) state.days = fromServer.days;
}

function formatBotMessage(raw) {
  const parts = [];
  for (const line of raw.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    const day = t.match(/^(?:#{1,3}\s*)?\*\*Jour\s*(\d+)\*\*/i);
    if (day) {
      parts.push(`<h3 class="day-heading">Jour ${day[1]}</h3>`);
      continue;
    }
    parts.push(`<p>${t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`);
  }
  return parts.join("");
}

function appendMessage(role, text) {
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
    const c = document.createElement("div");
    c.className = "message__content";
    c.innerHTML = formatBotMessage(text);
    bubble.appendChild(c);
  }
  wrap.appendChild(av);
  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function setLoading(on) {
  loaderEl.classList.toggle("hidden", !on);
  sendBtn.disabled = on;
  inputEl.disabled = on;
}

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

    if (data.version && data.version !== "2.1") {
      console.warn("Version serveur:", data.version);
    }
    mergeState(data.state);
    console.log("[state]", state, "session:", sessionId);

    if (data.version !== "2.1") {
      appendMessage("bot", "ERREUR: ancien serveur detecte. Arretez python et relancez server.py sur port 8081.");
    } else {
      appendMessage("bot", data.message);
    }
  } catch (err) {
    console.error(err);
    appendMessage("bot", "Erreur: python server.py puis http://127.0.0.1:8081");
  } finally {
    setLoading(false);
    inputEl.focus();
  }
});

startBtn.addEventListener("click", () => {
  landingEl.classList.add("landing--hidden");
  appEl.classList.remove("app--hidden");
  inputEl.focus();
});

document.getElementById("welcome")?.addEventListener("click", () => {
  inputEl.value = "3 jours a Sousse petit budget";
  inputEl.focus();
});
