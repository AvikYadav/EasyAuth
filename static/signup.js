function setMode(mode, btn) {
  const isLogin = mode === "login";

  document.getElementById("auth-form").action            = isLogin ? "/login"                  : "/signup";
  document.getElementById("heading").textContent         = isLogin ? "Welcome back"             : "Create account";
  document.getElementById("subtitle").textContent        = isLogin ? "Log in to your account."  : "Get started — it only takes a minute.";
  document.getElementById("submit-btn").textContent      = isLogin ? "Log in"                   : "Create account";
  document.getElementById("email-field").style.display   = isLogin ? "none"                     : "";
  document.getElementById("confirm-field").style.display = isLogin ? "none"                     : "";
  document.getElementById("email").required              = !isLogin;
  document.getElementById("confirm").required            = !isLogin;

  document.querySelectorAll(".tab").forEach(function(t) { t.classList.remove("active"); });
  btn.classList.add("active");
}

// Attach listeners via JS — no inline onclick, fully CSP compliant
document.querySelectorAll(".tab[data-mode]").forEach(function(btn) {
  btn.addEventListener("click", function() {
    setMode(btn.dataset.mode, btn);
  });
});