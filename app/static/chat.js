(() => {
  const form = document.getElementById("chat-form");
  const result = document.getElementById("result");
  const successPanel = document.getElementById("success-panel");
  const noticePanel = document.getElementById("notice-panel");
  const noticeEyebrow = document.getElementById("notice-eyebrow");
  const noticeTitle = document.getElementById("notice-title");
  const noticeBody = document.getElementById("notice-body");
  const noticeTips = document.getElementById("notice-tips");
  const suggestionList = document.getElementById("suggestion-list");
  const statusBadge = document.getElementById("status-badge");
  const reasonText = document.getElementById("reason-text");
  const answerBlock = document.getElementById("answer-block");
  const answerText = document.getElementById("answer-text");
  const citationsBlock = document.getElementById("citations-block");
  const citationsList = document.getElementById("citations-list");
  const errorText = document.getElementById("error-text");
  const submitBtn = document.getElementById("submit-btn");
  const questionInput = document.getElementById("question");

  const SUGGESTIONS = [
    "When is the next graduation ceremony?",
    "How does the campus shuttle bus work?",
    "Where can I get counselling support?",
    "How do academic appeals work for UNM students?",
  ];

  const REFUSAL_COPY = {
    off_topic: {
      tone: "soft",
      eyebrow: "Outside my lane",
      title: "I can only help with student affairs",
      body:
        "That question looks outside campus student services—things like graduation, registry, shuttle, counselling, exams, visa, and similar topics. Try rephrasing around student life on campus.",
      showTips: true,
    },
    insufficient_evidence: {
      tone: "soft",
      eyebrow: "Not enough in the documents",
      title: "I couldn’t find solid evidence for that",
      body:
        "I searched the published campus materials, but didn’t find enough reliable detail to answer safely. You could try a more specific question, or check the official Current Students pages.",
      showTips: true,
    },
    prompt_injection: {
      tone: "soft",
      eyebrow: "That request isn’t allowed",
      title: "I need to stay within campus Q&A",
      body:
        "I’m set up to answer student-affairs questions from campus documents—not to reveal system instructions or ignore those boundaries. Ask about services, policies, or campus life instead.",
      showTips: true,
    },
    generation_failed: {
      tone: "error",
      eyebrow: "Temporary hiccup",
      title: "I found material, but couldn’t finish the answer",
      body:
        "The language model didn’t respond successfully just now. Please try again in a moment. If it keeps happening, the API key or network may need a quick check.",
      showTips: false,
    },
  };

  const DEFAULT_REFUSAL = {
    tone: "soft",
    eyebrow: "I can’t answer that one",
    title: "Let’s try a student-affairs question",
    body:
      "I’m designed to stay grounded in campus student-affairs materials. Rephrase your question around graduation, transport, wellbeing, exams, or other student services.",
    showTips: true,
  };

  function showResultShell() {
    result.hidden = false;
    result.classList.remove("is-notice", "is-success");
    successPanel.hidden = true;
    noticePanel.hidden = true;
    noticeTips.hidden = true;
    suggestionList.replaceChildren();
    errorText.hidden = true;
    answerBlock.hidden = true;
    citationsBlock.hidden = true;
    citationsList.replaceChildren();
    reasonText.textContent = "";
  }

  function renderSuggestions() {
    suggestionList.replaceChildren();
    for (const tip of SUGGESTIONS) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion-chip";
      button.textContent = tip;
      button.addEventListener("click", () => {
        questionInput.value = tip;
        questionInput.focus();
      });
      suggestionList.append(button);
    }
  }

  function showNotice(copy) {
    result.classList.add("is-notice");
    noticePanel.hidden = false;
    noticePanel.className = "notice-panel";
    if (copy.tone === "error") {
      noticePanel.classList.add("is-error");
    } else {
      noticePanel.classList.add("is-soft-block");
    }
    noticeEyebrow.textContent = copy.eyebrow;
    noticeTitle.textContent = copy.title;
    noticeBody.textContent = copy.body;
    if (copy.showTips) {
      noticeTips.hidden = false;
      renderSuggestions();
    }
  }

  function showSuccess(payload) {
    result.classList.add("is-success");
    successPanel.hidden = false;
    statusBadge.textContent = "Answered";
    statusBadge.className = "badge";
    reasonText.textContent = "Grounded in campus materials";

    if (payload.answer) {
      answerBlock.hidden = false;
      answerText.textContent = payload.answer;
    }

    const citations = Array.isArray(payload.citations) ? payload.citations : [];
    if (citations.length) {
      citationsBlock.hidden = false;
      for (const citation of citations) {
        const item = document.createElement("li");
        const title = citation.title || citation.source_id || "source";
        if (citation.location && String(citation.location).startsWith("http")) {
          const link = document.createElement("a");
          link.href = String(citation.location).split("#")[0];
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = title;
          item.append(link);
          item.append(` — ${citation.location}`);
        } else {
          item.textContent = `${title} — ${citation.location || ""}`;
        }
        citationsList.append(item);
      }
    }
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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showResultShell();
    submitBtn.disabled = true;
    submitBtn.textContent = "Searching…";

    const email = document.getElementById("school-email").value.trim();
    const question = questionInput.value.trim();

    try {
      const response = await fetch("/api/v1/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-School-Email": email,
        },
        body: JSON.stringify({ question }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        showNotice({
          tone: "error",
          eyebrow: "Sign-in check",
          title: "I couldn’t verify your school email",
          body: detailMessage(payload.detail),
          showTips: false,
        });
        return;
      }

      if (payload.status === "refused") {
        const copy = REFUSAL_COPY[payload.reason] || DEFAULT_REFUSAL;
        showNotice(copy);
        return;
      }

      showSuccess(payload);
    } catch (error) {
      showNotice({
        tone: "error",
        eyebrow: "Connection issue",
        title: "I couldn’t reach the assistant just now",
        body: error instanceof Error ? error.message : "Network error. Please try again.",
        showTips: false,
      });
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Ask";
    }
  });
})();
