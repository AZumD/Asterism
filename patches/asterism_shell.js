/**
 * Asterism shell control — injected into SteamVR systemui.
 * Visibility/focus + optional Dashboard Manager pose bridge (loopback only).
 *
 * Does not own or terminate the desktop session.
 * Pose APIs require either:
 *   - reachable Frame via window.Dashboard (Phase 1), or
 *   - window.__ASTERISM_STEAMVR from a minimal hash-gated chunk bridge (Phase 2)
 */
(function () {
  "use strict";
  var OVERLAY_KEY = "asterism.desktop";
  var HTTP = "http://127.0.0.1:47831";
  var BTN_ID = "asterism-shell-desktop-btn";
  var DEBUG =
    true ||
    (typeof localStorage !== "undefined" &&
      localStorage.getItem("ASTERISM_DASHMGR_DEBUG") === "1");

  function log() {
    try {
      console.log.apply(
        console,
        ["[asterism-shell]"].concat([].slice.call(arguments))
      );
    } catch (_) {}
  }

  function postJson(path, obj) {
    try {
      fetch(HTTP + path, {
        method: "POST",
        mode: "cors",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(obj),
      })
        .then(function (r) {
          return r.json().catch(function () {
            return { ok: false, status: r.status };
          });
        })
        .then(function (j) {
          log("POST", path, j && j.ok);
        })
        .catch(function (e) {
          log("POST failed", path, String(e));
          // Fallback fire-and-forget (PNA may still block)
          try {
            fetch(HTTP + path, {
              method: "POST",
              mode: "no-cors",
              cache: "no-store",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(obj),
            });
          } catch (_) {}
        });
    } catch (e) {
      log("postJson error", e);
    }
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

  function safeNames(obj) {
    if (!obj) return null;
    var out = { keys: [], own: [], proto: [] };
    try {
      out.keys = Object.keys(obj);
    } catch (_) {}
    try {
      out.own = Object.getOwnPropertyNames(obj);
    } catch (_) {}
    try {
      var p = Object.getPrototypeOf(obj);
      if (p) out.proto = Object.getOwnPropertyNames(p);
    } catch (_) {}
    return out;
  }

  function looksAsterismKey(k) {
    return typeof k === "string" && k.indexOf("asterism.desktop") === 0;
  }

  function cloneTransform(xf) {
    if (!xf || typeof xf !== "object") return null;
    var t = xf.translation || {};
    var r = xf.rotation || {};
    var out = {
      translation: {
        x: Number(t.x),
        y: Number(t.y),
        z: Number(t.z),
      },
      rotation: {
        w: Number(r.w),
        x: Number(r.x),
        y: Number(r.y),
        z: Number(r.z),
      },
    };
    if (xf.scale != null) {
      if (typeof xf.scale === "object") {
        out.scale = {
          x: Number(xf.scale.x),
          y: Number(xf.scale.y),
          z: Number(xf.scale.z),
        };
      } else {
        out.scale = Number(xf.scale);
      }
    }
    return out;
  }

  function ywq() {
    var b = window.__ASTERISM_STEAMVR;
    if (b && b.yWq) return b.yWq;
    return null;
  }

  function ywqName(loc) {
    var e = ywq();
    if (!e) return String(loc);
    try {
      return e[loc] != null ? String(e[loc]) : String(loc);
    } catch (_) {
      return String(loc);
    }
  }

  function resolveFrames(overlayKey) {
    var frames = [];
    var bridge = window.__ASTERISM_STEAMVR;
    if (bridge && typeof bridge.getFramesForSummonKey === "function") {
      try {
        frames = bridge.getFramesForSummonKey(overlayKey) || [];
      } catch (e) {
        log("bridge getFramesForSummonKey failed", e);
      }
      return { source: "chunk_bridge", frames: frames };
    }

    // Phase 1: only window.Dashboard / known globals — no React fiber crawl.
    var dash = window.Dashboard;
    if (!dash) return { source: "none", frames: [], reason: "window.Dashboard missing" };

    var candidates = [];
    try {
      if (typeof dash.GetFramesWithAssociatedSummonKeys === "function") {
        candidates = dash.GetFramesWithAssociatedSummonKeys(overlayKey) || [];
        return { source: "Dashboard.GetFramesWithAssociatedSummonKeys", frames: candidates };
      }
    } catch (e) {
      log("Dashboard.GetFrames… failed", e);
    }

    // Legacy store / action store: name-only reachability (no deep walk)
    return {
      source: "window.Dashboard_only",
      frames: [],
      reason:
        "no GetFramesWithAssociatedSummonKeys on Dashboard; M.JJ is module-scoped",
    };
  }

  function frameSnapshot(frame) {
    if (!frame) return null;
    var dock = frame.docking;
    var map = dock && dock.m_mapLastRelativeTransformForDockLocation;
    var remembered = {};
    var e = ywq();
    var locations = e
      ? [e.Dashboard, e.World, e.Theater, e.LeftHand, e.RightHand, e.Boot]
      : [];
    if (map && typeof map.get === "function") {
      for (var i = 0; i < locations.length; i++) {
        var loc = locations[i];
        if (loc == null) continue;
        try {
          if (map.has && !map.has(loc)) continue;
          var xf = map.get(loc);
          if (xf) remembered[ywqName(loc)] = cloneTransform(xf);
        } catch (_) {}
      }
      // Also dump whatever keys exist if Map iterable
      try {
        if (typeof map.forEach === "function") {
          map.forEach(function (xf, loc) {
            var name = ywqName(loc);
            if (!remembered[name]) remembered[name] = cloneTransform(xf);
          });
        }
      } catch (_) {}
    }
    var scale = null;
    try {
      scale = frame.size && frame.size.scaleForActivePage;
    } catch (_) {}
    var keys = [];
    try {
      keys = (frame.associatedSummonOverlayKeys || []).slice();
    } catch (_) {}
    var summon = null;
    try {
      summon = frame.activePage && frame.activePage.summonOverlayKey;
    } catch (_) {}
    var dockLoc = null;
    try {
      dockLoc = dock && dock.dockLocation;
    } catch (_) {}
    return {
      frameID: frame.frameID != null ? String(frame.frameID) : null,
      associatedSummonOverlayKeys: keys,
      summonOverlayKey: summon,
      dockLocation: dockLoc,
      dockLocationName: ywqName(dockLoc),
      rememberedTransforms: remembered,
      scaleForActivePage: scale != null ? Number(scale) : null,
    };
  }

  function captureOverlay(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame) {
      return {
        ok: false,
        error: "no frame for overlay",
        overlay_key: overlayKey,
        resolve: resolved,
      };
    }
    var snap = frameSnapshot(frame);
    return {
      ok: true,
      overlay_key: overlayKey,
      resolve_source: resolved.source,
      capture: snap,
      world: (snap && snap.rememberedTransforms && snap.rememberedTransforms.World) || null,
    };
  }

  function seedWorld(overlayKey, transform) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var e = ywq();
    if (!e || e.World == null) {
      return { ok: false, error: "yWq.World unavailable (need chunk bridge)" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame || !frame.docking) {
      return { ok: false, error: "no frame/docking", resolve: resolved };
    }
    var map = frame.docking.m_mapLastRelativeTransformForDockLocation;
    if (!map || typeof map.set !== "function") {
      return { ok: false, error: "map missing" };
    }
    var plain = cloneTransform(transform);
    if (!plain) return { ok: false, error: "bad transform" };
    // Valve stores live transform objects; seed a plain deep copy.
    map.set(e.World, plain);
    return {
      ok: true,
      overlay_key: overlayKey,
      seeded: plain,
      after: frameSnapshot(frame),
    };
  }

  function setPresentation(overlayKey, mode) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var e = ywq();
    var loc = null;
    var name = String(mode || "").toLowerCase();
    if (e) {
      if (name === "dashboard") loc = e.Dashboard;
      else if (name === "world") loc = e.World;
      else if (name === "theater") loc = e.Theater;
      else if (name === "lefthand" || name === "left") loc = e.LeftHand;
      else if (name === "righthand" || name === "right") loc = e.RightHand;
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (frame && frame.docking && typeof frame.docking.SetDockLocation === "function" && loc != null) {
      try {
        frame.docking.SetDockLocation(loc);
        return {
          ok: true,
          path: "frame.docking.SetDockLocation",
          mode: name,
          after: frameSnapshot(frame),
        };
      } catch (err) {
        return { ok: false, error: String(err) };
      }
    }
    // Fallback: Dashboard mailbox handler (presentation only; no pose)
    try {
      var dash = window.Dashboard;
      if (dash && typeof dash.onVrCmdDockOverlayRequested === "function") {
        dash.onVrCmdDockOverlayRequested({
          overlay_key: overlayKey,
          dock_location: name,
        });
        return {
          ok: true,
          path: "Dashboard.onVrCmdDockOverlayRequested",
          mode: name,
          note: "presentation only; no map access",
        };
      }
    } catch (err2) {
      return { ok: false, error: String(err2) };
    }
    return { ok: false, error: "no SetDockLocation path", resolve: resolved };
  }

  function listAsterism() {
    var bridge = window.__ASTERISM_STEAMVR;
    var out = [];
    if (bridge && typeof bridge.listAsterismFrames === "function") {
      try {
        return bridge.listAsterismFrames();
      } catch (e) {
        log("listAsterismFrames failed", e);
      }
    }
    // Without bridge, try known PerWindow keys via capture attempts
    var keys = [];
    for (var i = 0; i < 8; i++) keys.push("asterism.desktop.app." + i);
    keys.unshift("asterism.desktop");
    for (var k = 0; k < keys.length; k++) {
      var c = captureOverlay(keys[k]);
      if (c.ok) out.push(c);
    }
    return out;
  }

  function runDashboardProbe() {
    var report = {
      ts: new Date().toISOString(),
      hasDashboard: !!window.Dashboard,
      hasAsterismBridge: !!window.__ASTERISM_STEAMVR,
      dashboard: safeNames(window.Dashboard),
      legacyStore: safeNames(window.LegacyDashboardStore),
      actionStore: safeNames(window.dashboardActionStore),
      globalActionsKeys: null,
      frameResolve: null,
      notes: [],
    };
    try {
      report.globalActionsKeys = Object.keys(window.globalActions || {});
    } catch (_) {}

    if (window.Dashboard) {
      var proto = report.dashboard && report.dashboard.proto;
      var interesting = [
        "GetFramesWithAssociatedSummonKeys",
        "GetFrame",
        "GetFrameWithTabId",
        "onVrCmdDockOverlayRequested",
        "frames",
        "activeFrame",
      ];
      report.dashboardHas = {};
      for (var i = 0; i < interesting.length; i++) {
        var name = interesting[i];
        var found = false;
        try {
          found =
            typeof window.Dashboard[name] !== "undefined" ||
            (proto && proto.indexOf(name) >= 0);
        } catch (_) {}
        report.dashboardHas[name] = found;
      }
      report.frameResolve = resolveFrames("asterism.desktop.app.2");
      if (
        report.frameResolve.source === "window.Dashboard_only" ||
        !(report.frameResolve.frames && report.frameResolve.frames.length)
      ) {
        report.notes.push(
          "Phase1: cannot resolve overlay→Frame via window.Dashboard alone; chunk bridge required for map read/seed"
        );
      } else {
        report.notes.push("Phase1: Frame resolve SUCCEEDED without chunk patch");
      }
    } else {
      report.notes.push("window.Dashboard not set yet");
    }

    // Static analysis note (from Valve setInitialTransformForLocation):
    report.notes.push(
      "Valve World map is consumed only when previous dock was LeftHand/RightHand; Dashboard→World uses requestSGTransform and ignores map[World]"
    );

    log("probe", report.notes.join(" | "));
    postJson("/dashmgr/probe", report);
    return report;
  }

  // ---- command poll loop (loopback Asterism service) ----
  var pollBusy = false;
  function pollCommands() {
    if (pollBusy) return;
    pollBusy = true;
    fetch(HTTP + "/dashmgr/poll", {
      method: "GET",
      mode: "cors",
      cache: "no-store",
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (msg) {
        if (!msg || !msg.cmd) return;
        var result;
        try {
          if (msg.cmd === "list") result = { ok: true, frames: listAsterism() };
          else if (msg.cmd === "probe") result = { ok: true, probe: runDashboardProbe() };
          else if (msg.cmd === "capture") result = captureOverlay(msg.overlay_key);
          else if (msg.cmd === "seed-world")
            result = seedWorld(msg.overlay_key, msg.transform);
          else if (msg.cmd === "set-presentation")
            result = setPresentation(msg.overlay_key, msg.mode);
          else result = { ok: false, error: "unknown cmd" };
        } catch (e) {
          result = { ok: false, error: String(e) };
        }
        postJson("/dashmgr/result", {
          id: msg.id,
          result: result,
        });
      })
      .catch(function () {
        /* service down / PNA — silent */
      })
      .finally(function () {
        pollBusy = false;
      });
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

  function waitDashboardThenProbe() {
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      if (window.Dashboard || tries > 60) {
        clearInterval(t);
        if (DEBUG) runDashboardProbe();
        // Expose narrow control surface for manual headset console if needed
        window.__ASTERISM_SHELL = {
          probe: runDashboardProbe,
          capture: captureOverlay,
          seedWorld: seedWorld,
          setPresentation: setPresentation,
          list: listAsterism,
        };
      }
    }, 500);
  }

  function boot() {
    inject();
    var obs = new MutationObserver(function () {
      if (!document.getElementById(BTN_ID)) inject();
    });
    if (document.body) {
      obs.observe(document.body, { childList: true, subtree: false });
    }
    waitDashboardThenProbe();
    setInterval(pollCommands, 750);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
