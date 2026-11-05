(() => {
  const body = document.body;
  const entryPath = body.dataset.entryPath || "";
  const form = document.getElementById("chat-form");
  const messageList = document.getElementById("message-list");
  const emailInput = document.getElementById("school-email");
  const questionInput = document.getElementById("question");
  const submitBtn = document.getElementById("submit-btn");
  const formError = document.getElementById("form-error");

  if (!form || !messageList || !emailInput || !questionInput || !submitBtn || !entryPath) {
    return;
  }

  const activeEmailKey = `unmc-chat:${entryPath}:active-email`;
  const openingNodes = [...messageList.childNodes].map((node) => node.cloneNode(true));
  const emailDomain = (body.dataset.emailDomain || "").trim().toLowerCase().replace(/^@/, "");
  let sessionId = "";
  let sessionEmail = "";
  let resumeToken = 0;
  let pendingResume = Promise.resolve(false);

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

  function scrollTranscript() {
    messageList.scrollTop = messageList.scrollHeight;
    const last = messageList.lastElementChild;
    if (last) {
      last.scrollIntoView({ block: "end" });
    }
  }

  function resetToOpening() {
    messageList.replaceChildren(...openingNodes.map((node) => node.cloneNode(true)));
    scrollTranscript();
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

  function appendBubble(role, content, citations) {
    const article = document.createElement("article");
    article.className = role === "user" ? "bubble bubble-user" : "bubble bubble-assistant";
    article.dataset.role = role;

    const label = document.createElement("span");
    label.className = "bubble-role";
    label.textContent = role === "user" ? "You" : "Assistant";

    const paragraph = document.createElement("p");
    paragraph.textContent = content;

    article.append(label, paragraph);

    const sources = Array.isArray(citations) ? citations : [];
    if (sources.length) {
      const list = document.createElement("ul");
      list.className = "bubble-sources";
      for (const citation of sources) {
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
      article.append(list);
    }

    messageList.append(article);
    scrollTranscript();
    return article;
  }

  function renderTranscript(messages) {
    messageList.replaceChildren();
    for (const message of messages) {
      if (!message || (message.role !== "user" && message.role !== "assistant")) continue;
      appendBubble(message.role, message.content || "", message.citations);
    }
    if (!messageList.childElementCount) {
      resetToOpening();
    }
  }

  function rememberSession() {
    const email = sessionEmail || normalizeEmail(emailInput.value);
    if (!email) return;
    sessionStorage.setItem(activeEmailKey, email);
    const key = storageKeyFor(email);
    if (!sessionId) {
      sessionStorage.removeItem(key);
      return;
    }
    sessionStorage.setItem(key, JSON.stringify({ sessionId, email }));
  }

  async function loadTranscript(email, nextSessionId, token) {
    const response = await fetch(
      `/api/v1/chat/${encodeURIComponent(entryPath)}/sessions/${encodeURIComponent(nextSessionId)}`,
      { headers: { "X-School-Email": email } },
    );
    if (token !== resumeToken) return false;
    if (!response.ok) {
      sessionId = "";
      sessionEmail = email;
      resetToOpening();
      sessionStorage.removeItem(storageKeyFor(email));
      return true;
    }
    const payload = await response.json().catch(() => ({}));
    if (token !== resumeToken) return false;
    sessionId = payload.session_id || nextSessionId;
    sessionEmail = email;
    if (Array.isArray(payload.messages) && payload.messages.length) {
      renderTranscript(payload.messages);
    } else {
      resetToOpening();
    }
    rememberSession();
    return true;
  }

  async function resumeForEmail(rawEmail) {
    const email = normalizeEmail(rawEmail);
    const token = ++resumeToken;
    if (!isSchoolEmail(email)) {
      return false;
    }
    sessionStorage.setItem(activeEmailKey, email);
    const response = await fetch(`/api/v1/chat/${encodeURIComponent(entryPath)}/sessions`, {
      headers: { "X-School-Email": email },
    });
    if (token !== resumeToken) return false;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      showError(detailMessage(payload.detail));
      return false;
    }
    clearError();
    const sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
    const latest = sessions[0];
    if (!latest || !latest.session_id) {
      sessionId = "";
      sessionEmail = email;
      resetToOpening();
      sessionStorage.removeItem(storageKeyFor(email));
      return true;
    }
    return loadTranscript(email, latest.session_id, token);
  }

  function scheduleResume(rawEmail) {
    submitBtn.disabled = true;
    pendingResume = resumeForEmail(rawEmail).finally(() => {
      submitBtn.disabled = false;
    });
    return pendingResume;
  }

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const email = normalizeEmail(emailInput.value);
    const message = questionInput.value.trim();
    if (!message) return;
    if (!isSchoolEmail(email)) {
      showError("Use a valid school email address.");
      return;
    }

    await pendingResume;
    if (sessionEmail !== email) {
      const ready = await scheduleResume(email);
      if (!ready) return;
    }

    const userBubble = appendBubble("user", message);
    const pending = appendBubble("assistant", "…");
    questionInput.value = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Sending…";

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
        if (response.status === 404) {
          sessionId = "";
          sessionEmail = email;
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
    } catch (error) {
      const note = pending.querySelector("p");
      if (note) {
        note.textContent = "I couldn’t reach the assistant just now. Please try again.";
      }
      showError(error instanceof Error ? error.message : "Network error. Please try again.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Send";
      questionInput.focus();
    }
  });

  emailInput.addEventListener("change", () => {
    scheduleResume(emailInput.value).catch(() => {
      showError("I couldn’t look up that conversation. Please try again.");
    });
  });

  const savedEmail = sessionStorage.getItem(activeEmailKey);
  if (savedEmail && isSchoolEmail(savedEmail)) {
    emailInput.value = savedEmail;
  }
  scheduleResume(emailInput.value).catch(() => {
    showError("I couldn’t look up that conversation. Please try again.");
  });
})();
