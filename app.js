(() => {
  "use strict";
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const sendButton = document.getElementById("send-button");
  const messages = document.getElementById("messages");
  const clearButton = document.getElementById("clear-chat");
  const charCount = document.getElementById("char-count");
  const statusLabel = document.getElementById("status-label");
  const statusDot = document.getElementById("status-dot");
  const notice = document.getElementById("notice");
  const sourcesArea = document.getElementById("sources-area");
  const sourceLinks = document.getElementById("source-links");
  const storageKey = "srit-assist-chat-v1";
  let history = [];
  let pending = false;

  function safeHistory() {
    try {
      const stored = JSON.parse(sessionStorage.getItem(storageKey) || "[]");
      return Array.isArray(stored) ? stored.filter(m => m && ["user", "assistant"].includes(m.role) && typeof m.content === "string").slice(-30) : [];
    } catch (_) { return []; }
  }
  function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(history.slice(-30))); } catch (_) { /* storage may be unavailable */ }
  }
  function scrollBottom() { messages.scrollTop = messages.scrollHeight; }
  function hideWelcome() {
    const welcome = document.getElementById("welcome-card");
    if (welcome) welcome.remove();
  }
  function createLink(label, url) {
    const a = document.createElement("a");
    a.textContent = label;
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }
  function appendSafeTextWithLinks(container, value) {
    // Only official SRIT HTTPS links are linkified; all other content is inserted as text.
    const pattern = /\[([^\]]{1,180})\]\((https:\/\/www\.srit\.ac\.in\/[^\s)]+)\)/g;
    let cursor = 0;
    const text = String(value || "");
    let match;
    while ((match = pattern.exec(text)) !== null) {
      container.appendChild(document.createTextNode(text.slice(cursor, match.index)));
      container.appendChild(createLink(match[1], match[2]));
      cursor = pattern.lastIndex;
    }
    container.appendChild(document.createTextNode(text.slice(cursor)));
  }
  function addMessage(role, content, options = {}) {
    hideWelcome();
    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "user" : "assistant"}`;
    if (role !== "user") {
      const avatar = document.createElement("div");
      avatar.className = "message-avatar";
      avatar.textContent = "SR";
      avatar.setAttribute("aria-hidden", "true");
      row.appendChild(avatar);
    }
    const wrap = document.createElement("div");
    wrap.className = "message-wrap";
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    appendSafeTextWithLinks(bubble, content);
    wrap.appendChild(bubble);
    if (options.meta) {
      const meta = document.createElement("div");
      meta.className = "message-meta";
      meta.textContent = options.meta;
      wrap.appendChild(meta);
    }
    row.appendChild(wrap);
    messages.appendChild(row);
    scrollBottom();
    return row;
  }
  function showTyping() {
    hideWelcome();
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.id = "typing-indicator";
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "SR";
    row.appendChild(avatar);
    const bubble = document.createElement("div");
    bubble.className = "message-bubble typing-bubble";
    bubble.setAttribute("aria-label", "Assistant is responding");
    for (let i = 0; i < 3; i++) bubble.appendChild(document.createElement("span"));
    row.appendChild(bubble);
    messages.appendChild(row);
    scrollBottom();
  }
  function removeTyping() { document.getElementById("typing-indicator")?.remove(); }
  function setPending(value) {
    pending = value;
    sendButton.disabled = value;
    sendButton.querySelector("span").textContent = value ? "Sending" : "Send";
    input.disabled = value;
  }
  function showNotice(text) {
    notice.textContent = text || "";
    notice.hidden = !text;
  }
  function showSources(sources) {
    sourceLinks.replaceChildren();
    const safeSources = Array.isArray(sources) ? sources.filter(s => s && typeof s.title === "string" && typeof s.url === "string" && /^https:\/\/www\.srit\.ac\.in\//.test(s.url)).slice(0, 4) : [];
    safeSources.forEach(source => {
      const a = createLink(source.title, source.url);
      a.className = "source-chip";
      sourceLinks.appendChild(a);
    });
    sourcesArea.hidden = safeSources.length === 0;
  }
  async function ask(question) {
    const text = String(question || "").trim();
    if (!text || pending) return;
    setPending(true);
    showNotice("");
    showSources([]);
    addMessage("user", text);
    history.push({ role: "user", content: text });
    persist();
    input.value = "";
    resizeInput();
    updateCount();
    showTyping();
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: history.slice(-8, -1) })
      });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error("The server returned an unexpected response. Please try again."); }
      removeTyping();
      if (!response.ok) throw new Error(data.error || "The enquiry could not be processed.");
      addMessage("assistant", data.answer || "I couldn't generate an answer. Please try again.", { meta: data.mode === "ai" ? "AI-assisted answer" : "Saved SRIT knowledge" });
      history.push({ role: "assistant", content: data.answer || "" });
      persist();
      if (data.note) showNotice(data.note);
      showSources(data.sources || []);
    } catch (error) {
      removeTyping();
      const message = error && error.message ? error.message : "Network error. Please try again.";
      addMessage("assistant", `${message}\n\nYou can also use the official SRIT website: https://www.srit.ac.in/`);
      history.push({ role: "assistant", content: message });
      persist();
      showNotice("Connection issue · If this is a newly deployed free server, it may need a moment to wake up.");
    } finally {
      setPending(false);
      input.focus();
      scrollBottom();
    }
  }
  function updateCount() { charCount.textContent = `${input.value.length} / 1200`; }
  function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 125)}px`;
  }
  function restoreHistory() {
    history = safeHistory();
    if (!history.length) return;
    hideWelcome();
    history.forEach(turn => addMessage(turn.role, turn.content));
  }
  async function loadStatus() {
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || data.status !== "ok") throw new Error("health check failed");
      if (data.ai_key_configured) {
        statusLabel.textContent = "AI key configured · fallback ready";
        statusDot.className = "status-dot";
      } else {
        statusLabel.textContent = "Knowledge mode · AI key not set";
        statusDot.className = "status-dot offline";
      }
    } catch (_) {
      statusLabel.textContent = "Assistant may be waking up";
      statusDot.className = "status-dot error";
    }
  }

  form.addEventListener("submit", event => { event.preventDefault(); ask(input.value); });
  input.addEventListener("input", () => { resizeInput(); updateCount(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!pending) ask(input.value);
    }
  });
  document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => ask(button.getAttribute("data-prompt"))));
  clearButton.addEventListener("click", () => {
    if (pending) return;
    history = [];
    try { sessionStorage.removeItem(storageKey); } catch (_) { /* ignore */ }
    window.location.reload();
  });

  restoreHistory();
  loadStatus();
  updateCount();
  input.focus({ preventScroll: true });
})();
