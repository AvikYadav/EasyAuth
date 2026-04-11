// ── Tab switching ─────────────────────────────────────────────────────────────

document.querySelectorAll(".detail-tab").forEach(function (tab) {
  tab.addEventListener("click", function () {
    document.querySelectorAll(".detail-tab").forEach(function (t) {
      t.classList.remove("active");
    });
    document.querySelectorAll(".tab-panel").forEach(function (p) {
      p.classList.remove("active");
    });

    tab.classList.add("active");
    document.getElementById("panel-" + tab.dataset.tab).classList.add("active");
  });
});

// ── Log entry expand / collapse ──────────────────────────────────────────────

document.addEventListener("click", function (e) {
  var entry = e.target.closest(".log-entry");
  if (!entry) return;

  var expanded = entry.dataset.expanded === "true";
  entry.dataset.expanded = expanded ? "false" : "true";
});

// ── HTML escape helper (prevents XSS when rendering AJAX content) ────────────

function esc(str) {
  if (str == null) return "";
  var div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

// ── Filter logs via AJAX ─────────────────────────────────────────────────────

var applyBtn = document.getElementById("apply-filters");
if (applyBtn) {
  applyBtn.addEventListener("click", function () {
    var service = this.dataset.service;
    var event   = document.getElementById("filter-event").value;
    var status  = document.getElementById("filter-status").value;
    var userId  = document.getElementById("filter-user").value.trim();

    var params = new URLSearchParams();
    if (event)  params.set("event", event);
    if (status) params.set("status", status);
    if (userId) params.set("user_id", userId);

    fetch("/dashboard/service/" + encodeURIComponent(service) + "/logs?" + params.toString())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === "success") {
          renderLogs(data.data.logs);
        }
      });
  });
}

function renderLogs(logs) {
  var container = document.getElementById("log-entries");

  if (!logs.length) {
    container.innerHTML = '<div class="empty-state-sm">No matching logs.</div>';
    return;
  }

  container.innerHTML = logs.map(function (log) {
    return (
      '<div class="log-entry" data-expanded="false">' +
        '<div class="log-entry-summary">' +
          '<span class="log-time mono">' + esc(log.timestamp) + '</span>' +
          '<span class="event-badge">' + esc(log.event) + '</span>' +
          '<span class="status-' + esc(log.status) + '">' + esc(log.status) + '</span>' +
          '<span class="log-user">' + esc(log.user_id || "\u2014") + '</span>' +
        '</div>' +
        '<div class="log-entry-detail">' +
          '<div class="log-detail-row"><span class="log-detail-key">IP</span><span>' + esc(log.ip || "\u2014") + '</span></div>' +
          '<div class="log-detail-row"><span class="log-detail-key">Error</span><span>' + esc(log.error_message || "\u2014") + '</span></div>' +
          '<div class="log-detail-row"><span class="log-detail-key">Metadata</span><span>' + esc(JSON.stringify(log.metadata || {})) + '</span></div>' +
        '</div>' +
      '</div>'
    );
  }).join("");
}

// ── Delete service (settings tab) ────────────────────────────────────────────

document.addEventListener("click", function (e) {
  var deleteBtn = e.target.closest(".btn-delete-service");
  if (!deleteBtn) return;

  var serviceName = deleteBtn.dataset.service;
  if (!confirm('Delete "' + serviceName + '"? This cannot be undone.')) return;

  fetch("/dashboard/delete-service/" + encodeURIComponent(serviceName), { method: "POST" })
    .then(function (res) {
      if (res.ok) window.location.href = "/dashboard";
      else alert("Failed to delete service.");
    });
});

// ── Reset apply button on bfcache restore (fixes "Applied!" stuck state) ─────
window.addEventListener("pageshow", function (e) {
  if (e.persisted) {
    var btn = document.getElementById("btn-apply-tpl");
    if (btn) {
      btn.textContent = "Apply \u0026 Open Editor";
      btn.disabled = false;
    }
  }
});

// ── Template Picker ──────────────────────────────────────────────────────────
(function () {
  var grid     = document.getElementById("template-grid");
  var actions  = document.getElementById("tpl-actions");
  var labelEl  = document.getElementById("tpl-selected-label");
  var applyBtn = document.getElementById("btn-apply-tpl");
  var svcEl    = document.querySelector("[data-service]");
  var SERVICE  = svcEl ? svcEl.dataset.service : "";

  if (!grid || !applyBtn) return;
  var selectedId = null;

  grid.addEventListener("click", function (e) {
    var card = e.target.closest(".template-card");
    if (!card) return;
    grid.querySelectorAll(".template-card").forEach(function (c) { c.classList.remove("active"); });
    card.classList.add("active");
    selectedId = card.dataset.templateId;
    var nm = card.querySelector(".tpl-card-name");
    labelEl.textContent = nm ? nm.textContent.trim() : selectedId;
    actions.style.display = "flex";
  });

  applyBtn.addEventListener("click", function () {
    if (!selectedId) return;
    if (!confirm('Apply "' + (labelEl.textContent || selectedId) + '"?\n\nThis replaces your current auth page design.')) return;
    applyBtn.textContent = "Applying...";
    applyBtn.disabled = true;
    fetch("/dashboard/service/" + encodeURIComponent(SERVICE) + "/apply-template", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id: selectedId }),
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) {
        applyBtn.textContent = "Applied!";
        setTimeout(function () { window.location.href = d.redirect; }, 400);
      } else {
        alert("Failed: " + (d.error || "Unknown error"));
        applyBtn.textContent = "Apply & Open Editor";
        applyBtn.disabled = false;
      }
    })
    .catch(function () {
      alert("Network error. Please try again.");
      applyBtn.textContent = "Apply & Open Editor";
      applyBtn.disabled = false;
    });
  });
}());
