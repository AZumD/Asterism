/**
 * Asterism shell control — injected into SteamVR systemui (Phase C).
 * Visibility/focus only. Does not own or terminate the desktop session.
 *
 * Invokes:
 *   1) VRHTML.VRClient.ShowDashboardOverlay({ overlayKey: "asterism.desktop" })
 *   2) best-effort HTTP POST to local asterism-dashboard (may be blocked by PNA)
 */
(function () {
  "use strict";
  var OVERLAY_KEY = "asterism.desktop";
  var HTTP = "http://127.0.0.1:47831";
  var BTN_ID = "asterism-shell-desktop-btn";

  function log() {
    try {
      console.log.apply(console, ["[asterism-shell]"].concat([].slice.call(arguments)));
    } catch (_) {}
  }

  function httpShow() {
    try {
      fetch(HTTP + "/show", { method: "POST", mode: "no-cors", cache: "no-store" });
    } catch (e) {
      log("http show failed", e);
    }
  }

  function showDesktop() {
    httpShow();
    try {
      var client = window.VRHTML && VRHTML.VRClient;
      if (client && typeof client.ShowDashboardOverlay === "function") {
        client.ShowDashboardOverlay({
          overlayKey: OVERLAY_KEY,
          sReason: "asterism_shell_desktop",
        });
        log("ShowDashboardOverlay", OVERLAY_KEY);
        return;
      }
    } catch (e) {
      log("ShowDashboardOverlay failed", e);
    }
    log("VRHTML.VRClient unavailable; relied on HTTP /show only");
  }

  function inject() {
    if (!document.body || document.getElementById(BTN_ID)) return;
    var btn = document.createElement("button");
    btn.id = BTN_ID;
    btn.type = "button";
    btn.textContent = "Desktop";
    btn.setAttribute("aria-label", "Asterism Desktop");
    btn.title = "Asterism Desktop (shell)";
    btn.style.cssText = [
      "position:fixed",
      "left:18px",
      "bottom:18px",
      "z-index:2147483646",
      "min-width:120px",
      "height:44px",
      "padding:0 18px",
      "border:1px solid rgba(255,255,255,0.25)",
      "border-radius:6px",
      "background:rgba(20,24,32,0.88)",
      "color:#e8eaed",
      "font:600 15px/44px Motiva Sans,Segoe UI,sans-serif",
      "letter-spacing:0.02em",
      "cursor:pointer",
      "pointer-events:auto",
      "box-shadow:0 2px 10px rgba(0,0,0,0.45)",
    ].join(";");
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      showDesktop();
    });
    document.body.appendChild(btn);
    log("Desktop shell control injected");
  }

  function boot() {
    inject();
    // Re-inject if React remounts body content
    var obs = new MutationObserver(function () {
      if (!document.getElementById(BTN_ID)) inject();
    });
    if (document.body) {
      obs.observe(document.body, { childList: true, subtree: false });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
