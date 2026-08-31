(() => {
  const form = document.getElementById("chat-form");
  const result = document.getElementById("result");
  const statusBadge = document.getElementById("status-badge");
  const reasonText = document.getElementById("reason-text");
  const answerBlock = document.getElementById("answer-block");
  const answerText = document.getElementById("answer-text");
  const citationsBlock = document.getElementById("citations-block");
  const citationsList = document.getElementById("citations-list");
  const errorText = document.getElementById("error-text");
  const submitBtn = document.getElementById("submit-btn");

  function showResultShell() {
    result.hidden = false;
    errorText.hidden = true;
    answerBlock.hidden = true;
    citationsBlock.hidden = true;
    citationsList.replaceChildren();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showResultShell();
    submitBtn.disabled = true;
    submitBtn.textContent = "Searching…";

    const email = document.getElementById("school-email").value.trim();
    const question = document.getElementById("question").value.trim();

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
        statusBadge.textContent = "error";
        statusBadge.className = "badge is-error";
        reasonText.textContent = payload.detail || `HTTP ${response.status}`;
        errorText.hidden = false;
        errorText.textContent = "Request failed. Check the email or try again later.";
        return;
      }

      const refused = payload.status === "refused";
      statusBadge.textContent = payload.status || "unknown";
      statusBadge.className = refused ? "badge is-refused" : "badge";
      reasonText.textContent = [payload.reason, payload.layer]
        .filter(Boolean)
        .join(" · ");

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
    } catch (error) {
      statusBadge.textContent = "error";
      statusBadge.className = "badge is-error";
      reasonText.textContent = "network_error";
      errorText.hidden = false;
      errorText.textContent = error instanceof Error ? error.message : "Network error";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Ask";
    }
  });
})();
