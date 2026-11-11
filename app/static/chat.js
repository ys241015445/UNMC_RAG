(() => {
  "use strict";

  const loginCard = document.getElementById("login-card");
  const loginForm = document.getElementById("login-form");
  const loginEmailInput = document.getElementById("login-email");
  const loginBtn = document.getElementById("login-btn");
  const loginError = document.getElementById("login-error");

  const chatCard = document.querySelector(".chat-card");
  const form = document.getElementById("chat-form");
  const chatLog = document.getElementById("chat-log");
  const questionInput = document.getElementById("question");
  const emailInput = document.getElementById("school-email");
  const emailBadge = document.getElementById("email-badge");
  const submitBtn = document.getElementById("submit-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const historyBtn = document.getElementById("history-btn");
  const historyMenu = document.getElementById("history-menu");

  const STORE = {
    conversations: "unmc_rag_conversations",
    email: "unmc_rag_email",
    active: "unmc_rag_active_conversation",
  };

  const MAX_HISTORY = 6;
  const MAX_CONTENT = 2000;

  const SUGGESTIONS = [
    "When is the next graduation ceremony?",
    "How does the campus shuttle bus work?",
    "Where can I get counselling support?",
    "How do academic appeals work for UNM students?",
  ];

  const REFUSAL_COPY = {
    off_topic: {
      eyebrow: "Outside my lane",
      title: "I can only help with student affairs",
      body:
        "That question looks outside campus student services—things like graduation, registry, shuttle, counselling, exams, visa, and similar topics. Try rephrasing around student life on campus.",
      showTips: true,
    },
    insufficient_evidence: {
      eyebrow: "Not enough in the documents",
      title: "I couldn’t find solid evidence for that",
      body:
        "I searched the published campus materials, but didn’t find enough reliable detail to answer safely. You could try a more specific question, or check the official Current Students pages.",
      showTips: true,
    },
    prompt_injection: {
      eyebrow: "That request isn’t allowed",
      title: "I need to stay within campus Q&A",
      body:
        "I’m set up to answer student-affairs questions from campus documents—not to reveal system instructions or ignore those boundaries. Ask about services, policies, or campus life instead.",
      showTips: true,
    },
    generation_failed: {
      eyebrow: "Temporary hiccup",
      title: "I found material, but couldn’t finish the answer",
      body:
        "The language model didn’t respond successfully just now. Please try again in a moment. If it keeps happening, the API key or network may need a quick check.",
      showTips: false,
    },
  };

  const DEFAULT_REFUSAL = {
    eyebrow: "I can’t answer that one",
    title: "Let’s try a student-affairs question",
    body:
      "I’m designed to stay grounded in campus student-affairs materials. Rephrase your question around graduation, transport, wellbeing, exams, or other student services.",
    showTips: true,
  };

  // ---------- state ----------

  let conversations = []; // {id, title, updatedAt, messages}
  let activeId = null;
  let serverMode = false; // true: history synced with database per email
  let currentEmail = "";
  let pending = false;

  function activeConversation() {
    return conversations.find((c) => c.id === activeId) || null;
  }

  function newId() {
    return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function ensureConversation() {
    let conv = activeConversation();
    if (!conv) {
      conv = {
        id: newId(),
        title: "",
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messages: [],
      };
      conversations.push(conv);
      activeId = conv.id;
    }
    return conv;
  }

  function touchConversation(conv) {
    conv.updatedAt = Date.now();
    if (!conv.title) {
      const firstUser = conv.messages.find((m) => m.role === "user");
      if (firstUser) conv.title = firstUser.content.slice(0, 60);
    }
    conversations.sort((a, b) => b.updatedAt - a.updatedAt);
    if (!serverMode) saveLocalConversations();
  }

  // ---------- local storage (offline fallback) ----------

  function conversationsKey() {
    return `${STORE.conversations}::${currentEmail}`;
  }

  function activeKey() {
    return `${STORE.active}::${currentEmail}`;
  }

  function loadLocalConversations() {
    try {
      const key = conversationsKey();
      let raw = localStorage.getItem(key);
      if (!raw) {
        const legacy = localStorage.getItem(STORE.conversations);
        if (legacy) {
          localStorage.setItem(key, legacy);
          localStorage.removeItem(STORE.conversations);
          raw = legacy;
        }
      }
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.filter((c) => c && Array.isArray(c.messages)) : [];
    } catch {
      return [];
    }
  }

  function saveLocalConversations() {
    try {
      localStorage.setItem(conversationsKey(), JSON.stringify(conversations));
    } catch {
      // Quota or privacy mode: keep the in-memory view working.
    }
  }

  function loadStoredEmail() {
    try {
      return localStorage.getItem(STORE.email) || "";
    } catch {
      return "";
    }
  }

  function saveStoredEmail(email) {
    try {
      if (email) localStorage.setItem(STORE.email, email);
      else localStorage.removeItem(STORE.email);
    } catch {
      // ignore
    }
  }

  function saveActiveId(id) {
    if (serverMode) return;
    try {
      if (id) localStorage.setItem(activeKey(), id);
      else localStorage.removeItem(activeKey());
    } catch {
      // ignore
    }
  }

  function loadActiveId() {
    if (serverMode) return null;
    try {
      const key = activeKey();
      const value = localStorage.getItem(key);
      if (!value) {
        const legacy = localStorage.getItem(STORE.active);
        if (legacy) {
          localStorage.setItem(key, legacy);
          localStorage.removeItem(STORE.active);
          return legacy;
        }
      }
      return value;
    } catch {
      return null;
    }
  }

  // ---------- server sync ----------

  function authHeaders() {
    return { "X-School-Email": currentEmail };
  }

  async function signIn(email) {
    const response = await fetch("/api/v1/conversations", {
      headers: { "X-School-Email": email },
    });

    if (response.ok) {
      const data = await response.json();
      serverMode = true;
      currentEmail = email;
      saveStoredEmail(email);
      conversations = (data.conversations || []).map((c) => ({
        id: c.id,
        title: c.title || "",
        updatedAt: Date.parse(c.updated_at) || Date.now(),
        messages: [],
      }));
      activeId = null;
      return { ok: true };
    }

    if (response.status === 503) {
      // Database unavailable: fall back to local-only history.
      serverMode = false;
      currentEmail = email;
      saveStoredEmail(email);
      conversations = loadLocalConversations();
      activeId = loadActiveId();
      return { ok: true, offline: true };
    }

    if (response.status === 401) {
      return { ok: false, error: "Use a valid school email address." };
    }

    return { ok: false, error: "Sign-in failed. Please try again in a moment." };
  }

  async function fetchConversationMessages(conv) {
    try {
      const response = await fetch(`/api/v1/conversations/${encodeURIComponent(conv.id)}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return;
      const data = await response.json();
      conv.messages = Array.isArray(data.messages) ? data.messages : [];
      if (data.title) conv.title = data.title;
    } catch {
      // Network hiccup: leave messages empty; user can retry.
    }
  }

  async function pushConversation(conv) {
    if (!serverMode) return;
    try {
      await fetch(`/api/v1/conversations/${encodeURIComponent(conv.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          title: conv.title || "",
          messages: conv.messages.map((m) => ({
            role: m.role,
            content: m.content,
            ...(m.status ? { status: m.status } : {}),
            ...(m.reason ? { reason: m.reason } : {}),
            ...(m.citations ? { citations: m.citations } : {}),
          })),
        }),
      });
    } catch {
      // Offline: conversation stays local; next send retries.
    }
  }

  // ---------- rendering ----------

  function showLogin(message) {
    loginError.textContent = message || "";
    loginError.hidden = !message;
    loginCard.hidden = false;
    chatCard.hidden = true;
    loginBtn.disabled = false;
    loginBtn.textContent = "Start chatting";
  }

  function showChat() {
    loginCard.hidden = true;
    chatCard.hidden = false;
    renderEmailField();
    renderConversation();
    autoGrow();
  }

  function scrollLog() {
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function renderSuggestions(target, onPick) {
    target.replaceChildren();
    for (const tip of SUGGESTIONS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion-chip";
      button.textContent = tip;
      button.addEventListener("click", () => onPick(tip));
      target.append(button);
    }
  }

  function renderEmptyState() {
    chatLog.replaceChildren();
    const shell = document.createElement("div");
    shell.id = "empty-state";
    shell.className = "empty-state";

    const title = document.createElement("p");
    title.className = "empty-title";
    title.textContent = "Ask about student affairs";
    const sub = document.createElement("p");
    sub.className = "empty-sub";
    sub.textContent = "Try one of these to start:";
    const chips = document.createElement("div");
    chips.className = "suggestion-list";
    renderSuggestions(chips, (tip) => {
      questionInput.value = tip;
      form.requestSubmit();
    });

    shell.append(title, sub, chips);
    chatLog.append(shell);
  }

  function citationLink(citation) {
    const title = citation.title || citation.source_id || "source";
    const item = document.createElement("li");
    if (citation.location && String(citation.location).startsWith("http")) {
      const link = document.createElement("a");
      link.href = String(citation.location).split("#")[0];
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = title;
      item.append(link);
    } else {
      item.textContent = citation.location ? `${title} — ${citation.location}` : title;
    }
    return item;
  }

  function buildAssistantBubble(message) {
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    if (message.status === "refused") {
      bubble.classList.add("is-refusal");
      const copy = REFUSAL_COPY[message.reason] || DEFAULT_REFUSAL;
      const eyebrow = document.createElement("p");
      eyebrow.className = "notice-eyebrow";
      eyebrow.textContent = copy.eyebrow;
      const title = document.createElement("p");
      title.className = "notice-title";
      title.textContent = copy.title;
      const body = document.createElement("p");
      body.className = "notice-body";
      body.textContent = copy.body;
      bubble.append(eyebrow, title, body);
      if (copy.showTips) {
        const tips = document.createElement("div");
        tips.className = "suggestion-list";
        renderSuggestions(tips, (tip) => {
          questionInput.value = tip;
          form.requestSubmit();
        });
        bubble.append(tips);
      }
      return bubble;
    }

    if (message.status === "error") {
      bubble.classList.add("is-error");
      const eyebrow = document.createElement("p");
      eyebrow.className = "notice-eyebrow";
      eyebrow.textContent = message.eyebrow || "Something went wrong";
      const body = document.createElement("p");
      body.className = "notice-body";
      body.textContent = message.content || "Please try again in a moment.";
      bubble.append(eyebrow, body);
      return bubble;
    }

    bubble.textContent = message.content || "";

    const citations = Array.isArray(message.citations) ? message.citations : [];
    if (citations.length) {
      const sources = document.createElement("div");
      sources.className = "bubble-sources";
      const label = document.createElement("p");
      label.className = "bubble-sources-label";
      label.textContent = "Sources";
      const list = document.createElement("ul");
      for (const citation of citations) list.append(citationLink(citation));
      sources.append(label, list);
      bubble.append(sources);
    }
    return bubble;
  }

  function appendMessage(message) {
    const empty = document.getElementById("empty-state");
    if (empty) empty.remove();

    const row = document.createElement("div");
    row.className = `msg msg-${message.role}`;

    if (message.role === "assistant") {
      row.append(buildAssistantBubble(message));
    } else {
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = message.content;
      row.append(bubble);
    }

    chatLog.append(row);
    scrollLog();
    return row;
  }

  function appendThinking() {
    const row = document.createElement("div");
    row.className = "msg msg-assistant";
    row.id = "thinking-row";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const dots = document.createElement("span");
    dots.className = "thinking-dots";
    dots.append(
      document.createElement("i"),
      document.createElement("i"),
      document.createElement("i"),
    );
    bubble.append(dots);
    row.append(bubble);
    chatLog.append(row);
    scrollLog();
  }

  function removeThinking() {
    document.getElementById("thinking-row")?.remove();
  }

  function renderConversation() {
    chatLog.replaceChildren();
    const conv = activeConversation();
    if (!conv || conv.messages.length === 0) {
      renderEmptyState();
      return;
    }
    for (const message of conv.messages) appendMessage(message);
    scrollLog();
  }

  function renderEmailField() {
    if (currentEmail) {
      emailInput.hidden = true;
      emailInput.required = false;
      emailBadge.hidden = false;
      emailBadge.textContent = `${currentEmail} (change)`;
    } else {
      emailInput.hidden = false;
      emailInput.required = true;
      emailBadge.hidden = true;
    }
  }

  function conversationSnippet(conv) {
    const last = conv.messages[conv.messages.length - 1];
    if (!last) return "";
    let text = String(last.content || "");
    if (!text && last.status === "refused") text = "Refusal notice";
    return text.length > 70 ? `${text.slice(0, 70)}…` : text;
  }

  function renderHistoryMenu() {
    historyMenu.replaceChildren();

    const head = document.createElement("div");
    head.className = "history-menu-head";
    const headTitle = document.createElement("p");
    headTitle.className = "history-menu-title";
    headTitle.textContent = serverMode
      ? `History — ${currentEmail}`
      : "History conversations";
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "history-clear-btn";
    clearBtn.textContent = "Clear all";
    clearBtn.addEventListener("click", () => {
      if (!conversations.length) return;
      if (!window.confirm("Delete all saved conversations? This cannot be undone.")) return;
      conversations = [];
      activeId = null;
      saveActiveId(null);
      if (!serverMode) saveLocalConversations();
      toggleHistoryMenu(false);
      renderConversation();
    });
    head.append(headTitle, clearBtn);
    historyMenu.append(head);

    const items = conversations
      .filter((c) => c.messages.length > 0 || serverMode)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 20);

    if (!items.length) {
      const empty = document.createElement("span");
      empty.className = "history-empty";
      empty.textContent = "No past conversations yet";
      historyMenu.append(empty);
      return;
    }

    for (const conv of items) {
      const item = document.createElement("div");
      item.className = `history-item${conv.id === activeId ? " is-active" : ""}`;

      const main = document.createElement("button");
      main.type = "button";
      main.className = "history-main";
      const title = document.createElement("span");
      title.className = "history-title";
      title.textContent = conv.title || "Untitled conversation";
      const snippet = document.createElement("span");
      snippet.className = "history-snippet";
      snippet.textContent = conversationSnippet(conv);
      const date = document.createElement("span");
      date.className = "history-date";
      date.textContent = new Date(conv.updatedAt).toLocaleString();
      main.append(title, snippet, date);
      main.addEventListener("click", () => openConversation(conv.id));

      const actions = document.createElement("div");
      actions.className = "history-actions";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "history-action-btn";
      renameBtn.textContent = "Rename";
      renameBtn.addEventListener("click", () => startHistoryRename(item, conv));

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "history-action-btn is-danger";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm(`Delete "${conv.title || "Untitled conversation"}"?`)) return;
        conversations = conversations.filter((c) => c.id !== conv.id);
        if (activeId === conv.id) {
          activeId = null;
          saveActiveId(null);
          renderConversation();
        }
        if (!serverMode) saveLocalConversations();
        renderHistoryMenu();
      });

      actions.append(renameBtn, deleteBtn);
      item.append(main, actions);
      historyMenu.append(item);
    }
  }

  function startHistoryRename(item, conv) {
    const main = item.querySelector(".history-main");
    if (!main || item.querySelector(".history-rename-input")) return;
    const input = document.createElement("input");
    input.className = "history-rename-input";
    input.type = "text";
    input.maxLength = 80;
    input.value = conv.title || "";
    main.replaceChildren(input);
    input.focus();
    input.select();

    const commit = () => {
      conv.title = input.value.trim() || conv.title || "Untitled conversation";
      conv.updatedAt = Date.now();
      if (!serverMode) saveLocalConversations();
      renderHistoryMenu();
      pushConversation(conv);
    };
    const cancel = () => renderHistoryMenu();

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        cancel();
      }
    });
    input.addEventListener("blur", commit);
  }

  async function openConversation(id) {
    const conv = conversations.find((c) => c.id === id);
    if (!conv) return;
    activeId = id;
    saveActiveId(id);
    toggleHistoryMenu(false);
    renderConversation();
    if (serverMode && (!conv.messages || conv.messages.length === 0)) {
      await fetchConversationMessages(conv);
      renderConversation();
    }
  }

  function toggleHistoryMenu(open) {
    historyMenu.hidden = !open;
    historyBtn.setAttribute("aria-expanded", String(open));
    if (open) renderHistoryMenu();
  }

  // ---------- chat request ----------

  function historyPayload(conv) {
    return conv.messages
      .slice(-MAX_HISTORY)
      .map((m) => ({ role: m.role, content: String(m.content).slice(0, MAX_CONTENT) }));
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

  async function sendQuestion(question) {
    if (pending || !question || !currentEmail) return;
    const conv = ensureConversation();
    appendMessage({ role: "user", content: question });
    conv.messages.push({ role: "user", content: question, createdAt: Date.now() });
    touchConversation(conv);
    questionInput.value = "";
    autoGrow();

    pending = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "Searching…";
    appendThinking();

    try {
      const response = await fetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ question, history: historyPayload(conv) }),
      });
      const payload = await response.json().catch(() => ({}));

      let assistantMessage;
      if (!response.ok) {
        assistantMessage = {
          role: "assistant",
          status: "error",
          eyebrow: "Sign-in check",
          content: detailMessage(payload.detail),
          createdAt: Date.now(),
        };
      } else if (payload.status === "refused") {
        assistantMessage = {
          role: "assistant",
          status: "refused",
          reason: payload.reason,
          createdAt: Date.now(),
        };
      } else {
        assistantMessage = {
          role: "assistant",
          status: "answered",
          content: payload.answer || "",
          citations: Array.isArray(payload.citations) ? payload.citations : [],
          createdAt: Date.now(),
        };
      }

      removeThinking();
      appendMessage(assistantMessage);
      conv.messages.push(assistantMessage);
      touchConversation(conv);
      pushConversation(conv);
    } catch (error) {
      removeThinking();
      const message =
        error instanceof Error ? error.message : "Network error. Please try again.";
      appendMessage({
        role: "assistant",
        status: "error",
        eyebrow: "Connection issue",
        content: message,
        createdAt: Date.now(),
      });
      conv.messages.push({
        role: "assistant",
        status: "error",
        content: message,
        createdAt: Date.now(),
      });
      touchConversation(conv);
    } finally {
      pending = false;
      submitBtn.disabled = false;
      submitBtn.textContent = "Ask";
      questionInput.focus();
    }
  }

  // ---------- events ----------

  function autoGrow() {
    questionInput.style.height = "auto";
    questionInput.style.height = `${Math.min(questionInput.scrollHeight, 128)}px`;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = loginEmailInput.value.trim();
    if (!email || loginBtn.disabled) return;
    loginBtn.disabled = true;
    loginBtn.textContent = "Checking…";
    loginError.hidden = true;
    try {
      const result = await signIn(email);
      if (result.ok) {
        showChat();
        if (result.offline) {
          // Storage is down: inform, but let local mode continue.
          setTimeout(
            () => window.alert("Database is unavailable — chat history will be kept on this device only."),
            50,
          );
        }
      } else {
        showLogin(result.error);
        loginEmailInput.focus();
      }
    } catch {
      showLogin("Network error. Please try again.");
      loginEmailInput.focus();
    }
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = questionInput.value.trim();
    if (question) sendQuestion(question);
  });

  questionInput.addEventListener("input", autoGrow);
  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  newChatBtn.addEventListener("click", () => {
    activeId = null;
    saveActiveId(null);
    toggleHistoryMenu(false);
    renderConversation();
    questionInput.focus();
  });

  historyBtn.addEventListener("click", () => toggleHistoryMenu(historyMenu.hidden));

  document.addEventListener("click", (event) => {
    if (
      !historyMenu.hidden &&
      !event.target.closest(".history-wrap") &&
      !event.target.closest("#history-menu")
    ) {
      toggleHistoryMenu(false);
    }
  });

  emailBadge.addEventListener("click", () => {
    activeId = null;
    conversations = [];
    currentEmail = "";
    saveStoredEmail("");
    renderHistoryMenu();
    toggleHistoryMenu(false);
    showLogin();
    loginEmailInput.value = "";
    loginEmailInput.focus();
  });

  // ---------- init ----------

  const stored = loadStoredEmail();
  if (stored) {
    loginEmailInput.value = stored;
    loginForm.requestSubmit();
  } else {
    showLogin();
    loginEmailInput.focus();
  }
})();
