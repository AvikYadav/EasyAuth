// ── Create overlay ────────────────────────────────────────────────────────────

var createOverlay = document.getElementById("create-overlay");

function openCreate() {
  createOverlay.classList.add("open");
}

function closeCreate() {
  createOverlay.classList.remove("open");
}

// ── Event listeners (CSP safe — no inline handlers) ──────────────────────────

// "+" New service button (header)
var btnNew = document.getElementById("btn-new-service");
if (btnNew) btnNew.addEventListener("click", openCreate);

// "Create your first service" button (empty state)
var btnEmpty = document.getElementById("btn-empty-create");
if (btnEmpty) btnEmpty.addEventListener("click", openCreate);

// Close button inside popup
var btnClose = document.getElementById("btn-close-create");
if (btnClose) btnClose.addEventListener("click", closeCreate);

// Click backdrop to close
createOverlay.addEventListener("click", function (e) {
  if (e.target === createOverlay) closeCreate();
});

// Escape key closes overlay
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") closeCreate();
});
