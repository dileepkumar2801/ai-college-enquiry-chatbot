const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const typing = document.getElementById("typing");
const sendButton = document.getElementById("send-button");
const welcome = document.getElementById("welcome");
const clearButton = document.getElementById("clear-chat");

function scrollToLatest() {
  messages.scrollTop = messages.scrollHeight;
}

function addMessage(text, role, meta = "") {
  welcome.classList.add("hidden");
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  if (role === "bot") {
    const avatar = document.createElement("div");
    avatar.className = "mini-avatar";
    avatar.textContent = "CM";
    avatar.setAttribute("aria-hidden", "true");
    row.appendChild(avatar);
  }

  const wrap = document.createElement("div");
  wrap.className = "message-wrap";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  // textContent prevents FAQ answers or user input from injecting HTML.
  bubble.textContent = text;
  wrap.appendChild(bubble);

  if (meta) {
    const metadata = document.createElement("div");
    metadata.className = "message-meta";
    metadata.textContent = meta;
    wrap.appendChild(metadata);
  }
  row.appendChild(wrap);
  messages.appendChild(row);
  scrollToLatest();
}

async function sendQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed || sendButton.disabled) return;

  addMessage(trimmed, "user");
  input.value = "";
  sendButton.disabled = true;
  typing.classList.remove("hidden");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Something went wrong. Please try again.");
    const meta = data.matched
      ? `${data.category} · Match score ${(data.confidence * 100).toFixed(0)}%`
      : "No reliable FAQ match";
    addMessage(data.answer, "bot", meta);
  } catch (error) {
    addMessage(error.message || "Unable to connect. Please check your connection and try again.", "bot");
  } finally {
    typing.classList.add("hidden");
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuestion(input.value);
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => sendQuestion(button.dataset.question));
});

clearButton.addEventListener("click", () => {
  messages.replaceChildren();
  welcome.classList.remove("hidden");
  input.focus();
});

async function loadSuggestions() {
  try {
    const response = await fetch("/api/suggestions");
    if (!response.ok) return;
    const questions = await response.json();
    const container = document.getElementById("suggestions");
    if (!Array.isArray(questions) || questions.length === 0) return;
    container.replaceChildren();
    questions.slice(0, 6).forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion";
      button.dataset.question = item.question;
      const label = document.createElement("span");
      label.textContent = item.question;
      const arrow = document.createElement("span");
      arrow.textContent = "↗";
      button.append(label, arrow);
      button.addEventListener("click", () => sendQuestion(item.question));
      container.appendChild(button);
    });
  } catch (_) {
    // The four static suggestions remain usable if the API is temporarily unavailable.
  }
}
loadSuggestions();
