function setMode(mode, btn) {
    document.getElementById("mode-input").value          = mode;
    document.getElementById("heading").textContent       = mode === "login" ? "Welcome back" : "Create account";
    document.getElementById("submit-btn").textContent    = mode === "login" ? "Log in" : "Create account";
    document.getElementById("email-field").style.display = mode === "login" ? "none" : "";
    document.getElementById("email").required            = mode === "signup";
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
}