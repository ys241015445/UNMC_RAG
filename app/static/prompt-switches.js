(() => {
  const switches = document.querySelectorAll("[data-switch]");

  function paint(button, enabled) {
    button.setAttribute("aria-checked", enabled ? "true" : "false");
    button.classList.toggle("is-on", enabled);
    const state = document.getElementById(`state-${button.dataset.switch}`);
    if (state) state.textContent = enabled ? "On" : "Off";
  }

  function showError(text) {
    const note = document.getElementById("switch-error");
    if (!note) return;
    note.hidden = false;
    note.textContent = text;
  }

  async function persist(button, enabled) {
    const path = button.dataset.switch;
    const previous = button.getAttribute("aria-checked") === "true";
    paint(button, enabled);
    try {
      const response = await fetch(`/prompts/${encodeURIComponent(path)}/enabled`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error("save failed");
      paint(button, Boolean(payload.enabled));
      const note = document.getElementById("switch-error");
      if (note) note.hidden = true;
    } catch {
      paint(button, previous);
      showError("Could not save that switch. Try again.");
    }
  }

  for (const button of switches) {
    let startX = 0;
    let moved = false;
    let tracking = false;

    button.addEventListener("pointerdown", (event) => {
      tracking = true;
      moved = false;
      startX = event.clientX;
      if (button.setPointerCapture) button.setPointerCapture(event.pointerId);
    });

    button.addEventListener("pointermove", (event) => {
      if (!tracking) return;
      if (Math.abs(event.clientX - startX) > 8) moved = true;
    });

    button.addEventListener("pointerup", (event) => {
      if (!tracking) return;
      tracking = false;
      const dx = event.clientX - startX;
      const wasOn = button.getAttribute("aria-checked") === "true";
      let enabled = !wasOn;
      if (moved && dx >= 10) enabled = true;
      else if (moved && dx <= -10) enabled = false;
      persist(button, enabled);
    });

    button.addEventListener("keydown", (event) => {
      const wasOn = button.getAttribute("aria-checked") === "true";
      if (event.key === "ArrowRight") {
        event.preventDefault();
        persist(button, true);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        persist(button, false);
      } else if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        persist(button, !wasOn);
      }
    });
  }
})();
