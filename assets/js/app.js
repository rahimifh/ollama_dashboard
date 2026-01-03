function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

async function streamNdjson({ url, method, headers, body, onJson, onError }) {
  try {
    const res = await fetch(url, { method, headers, body });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`.trim());
    }
    if (!res.body) throw new Error("Streaming not supported by this browser.");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line) continue;
        let obj;
        try {
          obj = JSON.parse(line);
        } catch (e) {
          throw new Error(`Bad JSON line: ${line}`);
        }
        onJson(obj);
      }
    }

    // Flush any remaining decoded text (e.g., if the final JSON line didn't end with \n).
    buffer += decoder.decode();
    const tail = buffer.trim();
    if (tail) {
      for (const raw of tail.split("\n")) {
        const line = raw.trim();
        if (!line) continue;
        onJson(JSON.parse(line));
      }
    }
  } catch (e) {
    if (onError) onError(e);
    else console.error(e);
  }
}

function formatPullProgress(obj) {
  if (obj.error) return `Error: ${obj.error}`;
  if (obj.status && obj.total && obj.completed) {
    const pct = Math.floor((obj.completed / obj.total) * 100);
    return `${obj.status} (${pct}%)`;
  }
  if (obj.status) return obj.status;
  return JSON.stringify(obj);
}

function wirePullForm() {
  const form = document.getElementById("pull-form");
  if (!form) return;

  const input = document.getElementById("pull-model");
  const progress = document.getElementById("pull-progress");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const model = (input && input.value ? input.value : "").trim();
    if (!model) return;

    progress.textContent = `Starting pull for ${model}...`;
    const csrftoken = getCookie("csrftoken");

    await streamNdjson({
      url: "/api/models/pull",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrftoken ? { "X-CSRFToken": csrftoken } : {}),
      },
      body: JSON.stringify({ model }),
      onJson: (obj) => {
        progress.textContent = formatPullProgress(obj);
        if (obj.status === "success" && window.htmx) {
          window.htmx.ajax("GET", "/partials/models/", { target: "#models-container" });
        }
      },
      onError: (err) => {
        progress.textContent = `Pull failed: ${err.message || err}`;
      },
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  wirePullForm();
  wireChatForm();
});

function scrollMessagesToBottom(messagesEl) {
  if (!messagesEl) return;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function makeMsgEl(role, content) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg--${role}`;

  const roleEl = document.createElement("div");
  roleEl.className = "msg__role mono";
  roleEl.textContent = role;

  const contentEl = document.createElement("div");
  contentEl.className = "msg__content";
  contentEl.textContent = content || "";

  wrap.appendChild(roleEl);
  wrap.appendChild(contentEl);
  return { wrap, contentEl };
}

function wireChatForm() {
  const form = document.getElementById("chat-form");
  if (!form) return;

  const messagesEl = document.getElementById("messages");
  const inputEl = document.getElementById("chat-input");
  const sessionIdEl = document.getElementById("chat-session-id");
  const statusEl = document.getElementById("chat-status");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const sessionId = sessionIdEl ? sessionIdEl.value : "";
    const content = inputEl ? inputEl.value.trim() : "";
    if (!sessionId || !content) return;

    const placeholder = document.getElementById("no-messages-placeholder");
    if (placeholder) placeholder.remove();

    const userMsg = makeMsgEl("user", content);
    messagesEl.appendChild(userMsg.wrap);
    scrollMessagesToBottom(messagesEl);

    if (inputEl) inputEl.value = "";

    const assistantMsg = makeMsgEl("assistant", "");
    messagesEl.appendChild(assistantMsg.wrap);
    scrollMessagesToBottom(messagesEl);

    const csrftoken = getCookie("csrftoken");
    let assistantText = "";
    if (statusEl) statusEl.textContent = "Thinking…";

    await streamNdjson({
      url: "/api/chat/stream",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrftoken ? { "X-CSRFToken": csrftoken } : {}),
      },
      body: JSON.stringify({ session_id: sessionId, content }),
      onJson: (obj) => {
        if (obj.error) {
          if (statusEl) statusEl.textContent = `Error: ${obj.error}`;
          assistantMsg.contentEl.textContent = assistantMsg.contentEl.textContent
            ? assistantMsg.contentEl.textContent
            : "(error)";
          return;
        }

        if (obj.delta) {
          assistantText += obj.delta;
          assistantMsg.contentEl.textContent = assistantText;
          scrollMessagesToBottom(messagesEl);
        }

        if (obj.done) {
          if (statusEl && !obj.error) statusEl.textContent = "";
        }
      },
      onError: (err) => {
        if (statusEl) statusEl.textContent = `Request failed: ${err.message || err}`;
      },
    });
  });
}


