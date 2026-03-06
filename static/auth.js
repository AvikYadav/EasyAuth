function setMode(mode, btn) {
  document.getElementById("mode-input").value           = mode;
  document.getElementById("heading").textContent        = mode === "login" ? "Welcome back"  : "Create account";
  document.getElementById("submit-btn").textContent     = mode === "login" ? "Log in"        : "Create account";
  document.getElementById("email-field").style.display  = mode === "login" ? "none"          : "";
  document.getElementById("email").required             = mode === "signup";

  document.querySelectorAll(".tab").forEach(function(t) { t.classList.remove("active"); });
  btn.classList.add("active");
}

// Attach listeners via JS — no inline onclick, fully CSP compliant
document.querySelectorAll(".tab[data-mode]").forEach(function(btn) {
  btn.addEventListener("click", function() {
    setMode(btn.dataset.mode, btn);
  });
});