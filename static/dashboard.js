// ── Create Overlay ────────────────────────────────────────────────────────────

function openCreate() {
  document.getElementById("create-overlay").classList.add("open");
}

function closeCreate(event) {
  if (event.target === document.getElementById("create-overlay")) {
    document.getElementById("create-overlay").classList.remove("open");
  }
}

// ── Edit Overlay ──────────────────────────────────────────────────────────────

function openEdit(serviceName, currentCallbackUrl) {
  document.getElementById("edit-service-title").textContent  = serviceName;
  document.getElementById("edit-service-name").value         = serviceName;
  document.getElementById("edit-callback-url").value         = currentCallbackUrl;
  document.getElementById("edit-overlay").classList.add("open");
}

function closeEdit(event) {
  if (event.target === document.getElementById("edit-overlay")) {
    document.getElementById("edit-overlay").classList.remove("open");
  }
}

// ── Close All (✕ button) ──────────────────────────────────────────────────────

function closeAll() {
  document.getElementById("create-overlay").classList.remove("open");
  document.getElementById("edit-overlay").classList.remove("open");
}

// ── Button clicks — event delegation (CSP safe) ───────────────────────────────

document.addEventListener("click", function (e) {

  // Edit button
  const editBtn = e.target.closest(".btn-edit");
  if (editBtn) {
    openEdit(editBtn.dataset.service, editBtn.dataset.callback);
    return;
  }

  // Delete button
  const deleteBtn = e.target.closest(".btn-delete");
  if (deleteBtn) {
    const serviceName = deleteBtn.dataset.service;
    if (!confirm(`Delete service "${serviceName}"? This cannot be undone.`)) return;

    fetch(`/dashboard/delete-service/${serviceName}`, { method: "POST" })
      .then(res => {
        if (res.ok) window.location.reload();
        else alert("Failed to delete service.");
      });
    return;
  }

});

// ── Keyboard: Escape closes overlays ─────────────────────────────────────────

document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") closeAll();
});