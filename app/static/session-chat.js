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

  const storageKey = `unmc-chat:${entryPath}`;
  const openingNodes = [...messageList.childNodes].map((node) => node.cloneNode(true));
  let sessionId = "";
  let sessionEmail = "";

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
    if (!sessionId) {
      sessionStorage.removeItem(storageKey);
      return;
    }
    sessionStorage.setItem(
      storageKey,
      JSON.stringify({ sessionId, email: sessionEmail || emailInput.value.trim() }),
    );
  }

  async function restoreSession() {
    let saved = null;
    try {
      saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    } catch {
      saved = null;
    }
    if (!saved || !saved.sessionId) return;
    if (saved.email) emailInput.value = saved.email;
    const response = await fetch(
      `/api/v1/chat/${encodeURIComponent(entryPath)}/sessions/${encodeURIComponent(saved.sessionId)}`,
      { headers: { "X-School-Email": emailInput.value.trim() } },
    );
    if (!response.ok) {
      sessionStorage.removeItem(storageKey);
      return;
    }
    const payload = await response.json().catch(() => ({}));
    sessionId = payload.session_id || saved.sessionId;
    sessionEmail = emailInput.value.trim();
    if (Array.isArray(payload.messages) && payload.messages.length) {
      renderTranscript(payload.messages);
    }
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

    const email = emailInput.value.trim();
    const message = questionInput.value.trim();
    if (!message) return;

    if (sessionId && sessionEmail && sessionEmail !== email) {
      sessionId = "";
      sessionEmail = "";
      resetToOpening();
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
          sessionEmail = "";
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

  restoreSession().catch(() => {
    sessionStorage.removeItem(storageKey);
  });
})();
