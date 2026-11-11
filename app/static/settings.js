(() => {
  "use strict";

  const form = document.getElementById("settings-form");
  const status = document.getElementById("settings-status");
  const saveBtn = document.getElementById("save-btn");

  function setStatus(message, isError) {
    status.textContent = message;
    status.classList.toggle("is-error", Boolean(isError));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setStatus("");
    saveBtn.disabled = true;
    saveBtn.textContent = "保存中…";

    const conditions = [...form.querySelectorAll("[data-entry-path]")].map((card) => ({
      entry_path: card.dataset.entryPath,
      persona: card.querySelector(".persona").value,
      rag_enabled: card.querySelector(".rag-enabled").checked,
    }));

    try {
      const response = await fetch("/api/v1/settings/conditions", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shared_rules: document.getElementById("shared-rules").value,
          shared_rules_without_rag: document.getElementById("shared-rules-off").value,
          conditions,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail;
        setStatus(typeof detail === "string" ? detail : "保存失败", true);
        return;
      }
      setStatus("已保存。下一轮对话会使用新的 prompt 和 RAG 开关。");
    } catch {
      setStatus("网络错误，没有保存。", true);
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "保存";
    }
  });
})();
