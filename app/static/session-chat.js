(() => {
  const body = document.body;
  const entryPath = body.dataset.entryPath || "";
  const signInForm = document.getElementById("signin-form");
  const signInError = document.getElementById("signin-error");
  const form = document.getElementById("chat-form");
  const messageList = document.getElementById("message-list");
  const emptyState = document.getElementById("empty-state");
  const historyHint = document.getElementById("history-hint");
  const emailInput = document.getElementById("school-email");
  const emailLabel = document.getElementById("signed-in-email");
  const questionInput = document.getElementById("question");
  const submitBtn = document.getElementById("submit-btn");
  const formError = document.getElementById("form-error");
  const newChatBtn = document.getElementById("new-chat");
  const historyToggle = document.getElementById("history-toggle");
  const historyPanel = document.getElementById("history-panel");
  const historyTitle = document.getElementById("history-title");
  const historyList = document.getElementById("history-list");
  const clearHistoryBtn = document.getElementById("clear-history");
  const changeEmailBtn = document.getElementById("change-email");
  const openingNode = document.getElementById("empty-opening");

  if (
    !signInForm ||
    !form ||
    !messageList ||
    !emptyState ||
    !emailInput ||
    !questionInput ||
    !submitBtn ||
    !entryPath
  ) {
    return;
  }

  const activeEmailKey = `unmc-chat:${entryPath}:active-email`;
  const emailDomain = (body.dataset.emailDomain || "").trim().toLowerCase().replace(/^@/, "");
  const openingText = (openingNode?.textContent || "").trim();
  let sessionId = "";
  let sessionEmail = "";
  let sessions = [];
  let sending = false;

  function normalizeEmail(value) {
    return value.trim().toLowerCase();
  }

  function storageKeyFor(email) {
    return `unmc-chat:${entryPath}:${normalizeEmail(email)}`;
  }

  function isSchoolEmail(value) {
    const email = normalizeEmail(value);
    const at = email.lastIndexOf("@");
    if (at <= 0 || !emailDomain) return false;
    return email.slice(at + 1) === emailDomain && email.slice(0, at).length > 0;
  }

  function showSignInError(text) {
    if (!signInError) return;
    signInError.hidden = false;
    signInError.textContent = text;
  }

  function clearSignInError() {
    if (!signInError) return;
    signInError.hidden = true;
    signInError.textContent = "";
  }

  function showError(text) {
    if (!formError) return;
    formError.hidden = false;
    formError.textContent = text;
  }

  function clearError() {
    if (!formError) return;
    formError.hidden = true;
    formError.textContent = "";
  }

  function detailMessage(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (typeof item === "object" && item?.msg ? item.msg : String(item)))
        .join(" ");
    }
    return "Please check the school email and try again.";
  }

  function scrollTranscript() {
    messageList.scrollTop = messageList.scrollHeight;
  }

  function syncEmpty() {
    const hasBubble = Boolean(messageList.querySelector(".bubble"));
    emptyState.hidden = hasBubble;
    messageList.classList.toggle("is-empty", !hasBubble);
    if (historyHint) {
      historyHint.hidden = hasBubble || sessions.length === 0;
    }
  }

  function showSignIn() {
    body.classList.remove("is-signed-in");
    setHistoryOpen(false);
  }

  function showChat() {
    body.classList.add("is-signed-in");
    if (emailLabel) emailLabel.textContent = sessionEmail;
    if (historyTitle) historyTitle.textContent = `History — ${sessionEmail}`;
    questionInput.focus();
  }

  function rememberSession() {
    if (!sessionEmail) return;
    sessionStorage.setItem(activeEmailKey, sessionEmail);
    const key = storageKeyFor(sessionEmail);
    if (!sessionId) {
      sessionStorage.removeItem(key);
      return;
    }
    sessionStorage.setItem(key, JSON.stringify({ sessionId, email: sessionEmail }));
  }

  function storedSessionId(email) {
    const raw = sessionStorage.getItem(storageKeyFor(email));
    if (!raw) return "";
    try {
      const parsed = JSON.parse(raw);
      return typeof parsed.sessionId === "string" ? parsed.sessionId : "";
    } catch (error) {
      return "";
    }
  }

  function renderRichText(element, text) {
    const pieces = String(text).split(/(\*\*[^*]+\*\*)/g);
    for (const piece of pieces) {
      if (piece.startsWith("**") && piece.endsWith("**") && piece.length > 4) {
        const strong = document.createElement("strong");
        strong.textContent = piece.slice(2, -2);
        element.append(strong);
      } else {
        element.append(document.createTextNode(piece));
      }
    }
  }

  function sourceKey(citation) {
    return citation.title || citation.source_id || String(citation.location || "").split("#")[0] || "source";
  }

  function appendBubble(role, content, citations, options) {
    const article = document.createElement("article");
    article.className = role === "user" ? "bubble bubble-user" : "bubble bubble-assistant";
    article.dataset.role = role;
    if (options && options.opening) article.dataset.opening = "true";
    if (options && options.pending) article.dataset.pending = "true";

    if (options && options.pending) {
      const typing = document.createElement("span");
      typing.className = "typing";
      typing.setAttribute("aria-label", "Searching");
      typing.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
      article.append(typing);
    } else {
      const paragraph = document.createElement("p");
      renderRichText(paragraph, content);
      article.append(paragraph);
    }

    const sources = Array.isArray(citations) ? citations : [];
    const seen = new Set();
    const unique = [];
    for (const citation of sources) {
      const key = sourceKey(citation);
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(citation);
    }
    if (unique.length) {
      const block = document.createElement("div");
      block.className = "sources-block";
      const label = document.createElement("p");
      label.className = "sources-label";
      label.textContent = "Sources";
      const list = document.createElement("ul");
      list.className = "bubble-sources";
      for (const citation of unique) {
        const item = document.createElement("li");
        const title = citation.title || citation.source_id || "source";
        if (citation.location && String(citation.location).startsWith("http")) {
          const link = document.createElement("a");
          link.href = String(citation.location).split("#")[0];
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = title;
          item.append(link);
        } else {
          item.textContent = title;
        }
        list.append(item);
      }
      block.append(label, list);
      article.append(block);
    }

    messageList.append(article);
    syncEmpty();
    scrollTranscript();
    return article;
  }

  function resetToOpening() {
    messageList.querySelectorAll(".bubble").forEach((node) => node.remove());
    syncEmpty();
  }

  function renderTranscript(messages) {
    messageList.querySelectorAll(".bubble").forEach((node) => node.remove());
    for (const message of messages) {
      if (!message || (message.role !== "user" && message.role !== "assistant")) continue;
      appendBubble(message.role, message.content || "", message.citations);
    }
    if (!messageList.querySelector(".bubble")) resetToOpening();
    syncEmpty();
    renderHistory();
  }

  function formatWhen(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  }

  function renderHistory() {
    if (!historyList) return;
    historyList.replaceChildren();
    if (!sessions.length) {
      const empty = document.createElement("li");
      empty.className = "history-empty";
      empty.textContent = "No saved conversations yet.";
      historyList.append(empty);
      syncEmpty();
      return;
    }
    for (const session of sessions) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-item";
      if (session.session_id === sessionId) button.classList.add("is-current");
      const title = document.createElement("span");
      title.className = "history-item-title";
      title.textContent = session.title || "Conversation";
      button.append(title);
      if (session.preview) {
        const preview = document.createElement("span");
        preview.className = "history-item-preview";
        preview.textContent = session.preview;
        button.append(preview);
      }
      const when = formatWhen(session.updated_at || session.created_at);
      if (when) {
        const time = document.createElement("time");
        time.dateTime = session.updated_at || session.created_at || "";
        time.textContent = when;
        button.append(time);
      }
      button.addEventListener("click", () => {
        loadTranscript(session.session_id).catch(() => {
          showError("I couldn’t open that conversation. Please try again.");
        });
      });
      item.append(button);
      historyList.append(item);
    }
    syncEmpty();
  }

  function setHistoryOpen(open) {
    if (!historyPanel || !historyToggle) return;
    historyPanel.hidden = !open;
    historyToggle.setAttribute("aria-expanded", open ? "true" : "false");
    historyToggle.classList.toggle("is-open", open);
  }

  async function loadSessions() {
    const response = await fetch(`/api/v1/chat/${encodeURIComponent(entryPath)}/sessions`, {
      headers: { "X-School-Email": sessionEmail },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      showError(detailMessage(payload.detail));
      sessions = [];
      renderHistory();
      return false;
    }
    clearError();
    sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
    renderHistory();
    return true;
  }

  async function loadTranscript(nextSessionId) {
    const response = await fetch(
      `/api/v1/chat/${encodeURIComponent(entryPath)}/sessions/${encodeURIComponent(nextSessionId)}`,
      { headers: { "X-School-Email": sessionEmail } },
    );
    if (!response.ok) {
      sessionId = "";
      rememberSession();
      resetToOpening();
      return false;
    }
    const payload = await response.json().catch(() => ({}));
    sessionId = payload.session_id || nextSessionId;
    rememberSession();
    if (Array.isArray(payload.messages) && payload.messages.length) {
      renderTranscript(payload.messages);
    } else {
      resetToOpening();
    }
    if (window.matchMedia("(max-width: 720px)").matches) setHistoryOpen(false);
    return true;
  }

  function startNewChat() {
    sessionId = "";
    rememberSession();
    clearError();
    questionInput.value = "";
    resetToOpening();
    renderHistory();
    questionInput.focus();
  }

  async function enterChat(rawEmail, resumeStored) {
    const email = normalizeEmail(rawEmail);
    if (!isSchoolEmail(email)) {
      showSignInError("Use a valid school email address.");
      showSignIn();
      return false;
    }
    clearSignInError();
    sessionEmail = email;
    emailInput.value = email;
    sessionStorage.setItem(activeEmailKey, email);
    showChat();
    const ready = await loadSessions();
    if (!ready) return false;
    if (resumeStored) {
      const saved = storedSessionId(email);
      if (saved && sessions.some((session) => session.session_id === saved)) {
        await loadTranscript(saved);
        return true;
      }
    }
    sessionId = "";
    rememberSession();
    resetToOpening();
    return true;
  }

  function ensureOpeningBubble() {
    if (!openingText || messageList.querySelector("[data-opening='true']")) return;
    const bubble = appendBubble("assistant", openingText, [], { opening: true });
    messageList.insertBefore(bubble, messageList.firstChild);
  }

  async function sendMessage(rawMessage) {
    if (sending) return;
    clearError();
    const email = sessionEmail || normalizeEmail(emailInput.value);
    const message = rawMessage.trim();
    if (!message) return;
    if (!isSchoolEmail(email)) {
      showError("Use a valid school email address.");
      return;
    }

    const createdHere = !sessionId;
    sending = true;
    if (createdHere) ensureOpeningBubble();
    const userBubble = appendBubble("user", message);
    const pending = appendBubble("assistant", "", [], { pending: true });
    questionInput.value = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Searching...";

    try {
      const response = await fetch(`/api/v1/chat/${encodeURIComponent(entryPath)}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-School-Email": email,
        },
        body: JSON.stringify({
          message,
          session_id: sessionId || null,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        userBubble.remove();
        pending.remove();
        if (createdHere) messageList.querySelector("[data-opening='true']")?.remove();
        syncEmpty();
        if (response.status === 404) {
          sessionId = "";
          rememberSession();
        }
        showError(detailMessage(payload.detail));
        questionInput.value = message;
        return;
      }

      sessionId = payload.session_id || sessionId;
      sessionEmail = email;
      rememberSession();
      const answer = typeof payload.answer === "string" ? payload.answer.trim() : "";
      const answerText =
        answer || "I cannot answer that. Please try a campus student-services question.";
      pending.remove();
      appendBubble("assistant", answerText, payload.citations);
      await loadSessions();
    } catch (error) {
      pending.remove();
      appendBubble("assistant", "I couldn’t reach the assistant just now. Please try again.");
      showError(error instanceof Error ? error.message : "Network error. Please try again.");
    } finally {
      sending = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "Ask";
      questionInput.focus();
    }
  }

  signInForm.addEventListener("submit", (event) => {
    event.preventDefault();
    enterChat(emailInput.value, false).catch(() => {
      showSignInError("I couldn’t look up that conversation. Please try again.");
    });
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(questionInput.value);
  });

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  document.querySelectorAll("[data-suggestion]").forEach((button) => {
    button.addEventListener("click", () => {
      const text = button.getAttribute("data-suggestion") || "";
      sendMessage(text);
    });
  });

  newChatBtn?.addEventListener("click", startNewChat);

  historyToggle?.addEventListener("click", () => {
    const open = historyPanel ? historyPanel.hidden : false;
    setHistoryOpen(open);
  });

  clearHistoryBtn?.addEventListener("click", async () => {
    if (!sessionEmail) return;
    if (!window.confirm("Clear every saved conversation for this email on this page?")) return;
    clearError();
    try {
      const response = await fetch(`/api/v1/chat/${encodeURIComponent(entryPath)}/sessions`, {
        method: "DELETE",
        headers: { "X-School-Email": sessionEmail },
      });
      if (!response.ok && response.status !== 204) {
        const payload = await response.json().catch(() => ({}));
        showError(detailMessage(payload.detail) || "I couldn’t clear the history.");
        return;
      }
      sessions = [];
      startNewChat();
      renderHistory();
    } catch (error) {
      showError("I couldn’t clear the history. Please try again.");
    }
  });

  changeEmailBtn?.addEventListener("click", () => {
    showSignIn();
    emailInput.focus();
    emailInput.select();
  });

  const savedEmail = sessionStorage.getItem(activeEmailKey);
  if (savedEmail && isSchoolEmail(savedEmail)) {
    emailInput.value = savedEmail;
    enterChat(savedEmail, true).catch(() => {
      showError("I couldn’t look up that conversation. Please try again.");
    });
  } else {
    showSignIn();
  }
})();
