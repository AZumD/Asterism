/**
 * Asterism shell control — injected into SteamVR systemui.
 * Visibility/focus + Dashboard Manager pose bridge via ws://localhost (CSP-safe).
 *
 * Does not own or terminate the desktop session.
 * Pose APIs require window.__ASTERISM_STEAMVR from the hash-gated chunk bridge.
 */
(function () {
  "use strict";
  var OVERLAY_KEY = "asterism.desktop";
  var HTTP = "http://127.0.0.1:47831";
  // CSP connect-src allows ws://localhost:* — do NOT use 127.0.0.1 here.
  var WS_URL = "ws://localhost:47832";
  var BTN_ID = "asterism-shell-desktop-btn";
  var DEBUG =
    true ||
    (typeof localStorage !== "undefined" &&
      localStorage.getItem("ASTERISM_DASHMGR_DEBUG") === "1");

  var ws = null;
  var wsReconnectTimer = null;
  var wsBackoffMs = 1000;

  function log() {
    try {
      console.log.apply(
        console,
        ["[asterism-shell]"].concat([].slice.call(arguments))
      );
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

    var dash = window.Dashboard;
    if (!dash) return { source: "none", frames: [], reason: "window.Dashboard missing" };

    try {
      if (typeof dash.GetFramesWithAssociatedSummonKeys === "function") {
        return {
          source: "Dashboard.GetFramesWithAssociatedSummonKeys",
          frames: dash.GetFramesWithAssociatedSummonKeys(overlayKey) || [],
        };
      }
    } catch (e) {
      log("Dashboard.GetFrames… failed", e);
    }

    return {
      source: "window.Dashboard_only",
      frames: [],
      reason:
        "no GetFramesWithAssociatedSummonKeys on Dashboard; M.JJ is module-scoped",
    };
  }

  /** JSON-safe Frame resolve (never embed raw Valve Frame objects). */
  function resolveFramesReport(overlayKey) {
    var resolved = resolveFrames(overlayKey);
    var frames = resolved.frames || [];
    var snaps = [];
    for (var i = 0; i < frames.length; i++) {
      snaps.push(frameSnapshot(frames[i]));
    }
    var out = {
      source: resolved.source || "none",
      count: snaps.length,
      frames: snaps,
    };
    if (resolved.reason) out.reason = resolved.reason;
    return out;
  }

  function compareTransforms(a, b) {
    if (!a || !b) return { ok: false, error: "missing transform" };
    var ta = a.translation || {};
    var tb = b.translation || {};
    var dx = Number(ta.x) - Number(tb.x);
    var dy = Number(ta.y) - Number(tb.y);
    var dz = Number(ta.z) - Number(tb.z);
    var translationError = Math.sqrt(dx * dx + dy * dy + dz * dz);
    var ra = a.rotation || {};
    var rb = b.rotation || {};
    var dot =
      Number(ra.w) * Number(rb.w) +
      Number(ra.x) * Number(rb.x) +
      Number(ra.y) * Number(rb.y) +
      Number(ra.z) * Number(rb.z);
    if (dot > 1) dot = 1;
    if (dot < -1) dot = -1;
    var angleErrorRad = 2 * Math.acos(Math.abs(dot));
    var scaleError = null;
    if (a.scale != null && b.scale != null) {
      var sa =
        typeof a.scale === "object"
          ? [Number(a.scale.x), Number(a.scale.y), Number(a.scale.z)]
          : [Number(a.scale), Number(a.scale), Number(a.scale)];
      var sb =
        typeof b.scale === "object"
          ? [Number(b.scale.x), Number(b.scale.y), Number(b.scale.z)]
          : [Number(b.scale), Number(b.scale), Number(b.scale)];
      scaleError = Math.sqrt(
        Math.pow(sa[0] - sb[0], 2) +
          Math.pow(sa[1] - sb[1], 2) +
          Math.pow(sa[2] - sb[2], 2)
      );
    }
    return {
      ok: true,
      translationError: translationError,
      angleErrorRad: angleErrorRad,
      angleErrorDeg: (angleErrorRad * 180) / Math.PI,
      scaleError: scaleError,
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
      try {
        if (typeof map.forEach === "function") {
          map.forEach(function (xf2, loc2) {
            var name = ywqName(loc2);
            if (!remembered[name]) remembered[name] = cloneTransform(xf2);
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
    var report = resolveFramesReport(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame) {
      return {
        ok: false,
        error: "no frame for overlay",
        overlay_key: overlayKey,
        resolve: report,
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
      return {
        ok: false,
        error: "no frame/docking",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var map = frame.docking.m_mapLastRelativeTransformForDockLocation;
    if (!map || typeof map.set !== "function") {
      return { ok: false, error: "map missing" };
    }
    var plain = cloneTransform(transform);
    if (!plain) return { ok: false, error: "bad transform" };
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
    return {
      ok: false,
      error: "no SetDockLocation path",
      resolve: resolveFramesReport(overlayKey),
    };
  }

  function directRestore(overlayKey, transform) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var bridge = window.__ASTERISM_STEAMVR;
    if (!bridge || typeof bridge.applyWorldTransformForSummonKey !== "function") {
      return {
        ok: false,
        error:
          "applyWorldTransformForSummonKey unavailable (need chunk bridge v2)",
        bridgeVersion: bridge && bridge.version,
      };
    }
    var plain = cloneTransform(transform);
    if (!plain) return { ok: false, error: "bad transform" };
    var applied;
    try {
      applied = bridge.applyWorldTransformForSummonKey(overlayKey, plain);
    } catch (e) {
      return { ok: false, error: String(e) };
    }
    var live = null;
    if (typeof bridge.getLiveWorldTransformForSummonKey === "function") {
      try {
        live = bridge.getLiveWorldTransformForSummonKey(overlayKey);
      } catch (_) {}
    }
    var cap = captureOverlay(overlayKey);
    var compare = null;
    if (live && live.ok && live.xfTransform) {
      compare = compareTransforms(plain, live.xfTransform);
    }
    return {
      ok: !!(applied && applied.ok),
      path: (applied && applied.path) || "direct-restore",
      applied: applied,
      live: live,
      capture: cap.ok ? cap.capture : null,
      dockLocationName:
        cap.ok && cap.capture ? cap.capture.dockLocationName : null,
      compare: compare,
      note:
        "direct World xfTransform restore is experimental until live-validated",
    };
  }

  function getLiveWorld(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var bridge = window.__ASTERISM_STEAMVR;
    if (!bridge || typeof bridge.getLiveWorldTransformForSummonKey !== "function") {
      return {
        ok: false,
        error: "getLiveWorldTransformForSummonKey unavailable (need chunk bridge v2)",
        bridgeVersion: bridge && bridge.version,
      };
    }
    try {
      return bridge.getLiveWorldTransformForSummonKey(overlayKey);
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  /** Diagnostic oracle: seed map[World] then LeftHand -> World. Not normal boot. */
  function restoreViaHand(overlayKey, transform) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var seed = seedWorld(overlayKey, transform);
    if (!seed.ok) {
      return { ok: false, error: "seed failed", seed: seed, path: "restore-via-hand" };
    }
    var left = setPresentation(overlayKey, "lefthand");
    if (!left.ok) {
      return {
        ok: false,
        error: "LeftHand dock failed",
        seed: seed,
        lefthand: left,
        path: "restore-via-hand",
      };
    }
    var world = setPresentation(overlayKey, "world");
    return {
      ok: !!(world && world.ok),
      path: "restore-via-hand",
      seed: seed,
      lefthand: left,
      world: world,
      after: world && world.after,
      note: "diagnostic/fallback only; visibly docks to controller briefly",
    };
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
      transport: "websocket",
      wsUrl: WS_URL,
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
      report.frameResolve = resolveFramesReport("asterism.desktop.app.2");
      report.bridgeVersion =
        window.__ASTERISM_STEAMVR && window.__ASTERISM_STEAMVR.version;
      report.hasDirectApply =
        !!(
          window.__ASTERISM_STEAMVR &&
          typeof window.__ASTERISM_STEAMVR.applyWorldTransformForSummonKey ===
            "function"
        );
      if (
        report.frameResolve.source === "window.Dashboard_only" ||
        !(report.frameResolve.count > 0)
      ) {
        report.notes.push(
          "Phase1: cannot resolve overlay→Frame via window.Dashboard alone; chunk bridge required for map read/seed"
        );
      } else {
        report.notes.push("Frame resolve via " + report.frameResolve.source);
      }
    } else {
      report.notes.push("window.Dashboard not set yet");
    }

    report.notes.push(
      "Valve World map is consumed only when previous dock was LeftHand/RightHand; Dashboard→World uses requestSGTransform and ignores map[World]"
    );

    log("probe", report.notes.join(" | "));
    return report;
  }

  function handleCommand(msg) {
    var result;
    try {
      if (msg.cmd === "list") result = { ok: true, frames: listAsterism() };
      else if (msg.cmd === "probe") result = { ok: true, probe: runDashboardProbe() };
      else if (msg.cmd === "capture") result = captureOverlay(msg.overlay_key);
      else if (msg.cmd === "seed-world")
        result = seedWorld(msg.overlay_key, msg.transform);
      else if (msg.cmd === "set-presentation")
        result = setPresentation(msg.overlay_key, msg.mode);
      else if (msg.cmd === "direct-restore")
        result = directRestore(msg.overlay_key, msg.transform);
      else if (msg.cmd === "restore-via-hand")
        result = restoreViaHand(msg.overlay_key, msg.transform);
      else if (msg.cmd === "get-live-world")
        result = getLiveWorld(msg.overlay_key);
      else result = { ok: false, error: "unknown cmd" };
    } catch (e) {
      result = { ok: false, error: String(e) };
    }
    return result;
  }

  function wsSend(obj) {
    if (!ws || ws.readyState !== 1) return false;
    try {
      ws.send(JSON.stringify(obj));
      return true;
    } catch (e) {
      log("ws send failed", e);
      return false;
    }
  }

  function scheduleReconnect() {
    if (wsReconnectTimer) return;
    var delay = wsBackoffMs;
    wsReconnectTimer = setTimeout(function () {
      wsReconnectTimer = null;
      connectWs();
    }, delay);
    wsBackoffMs = Math.min(5000, Math.floor(wsBackoffMs * 1.5));
  }

  function connectWs() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      log("WebSocket construct failed", e);
      scheduleReconnect();
      return;
    }
    ws.onopen = function () {
      wsBackoffMs = 1000;
      log("WebSocket connected", WS_URL);
      wsSend({ type: "hello", client: "systemui", version: 1 });
    };
    ws.onmessage = function (ev) {
      var msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (_) {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "pong") return;
      if (msg.type === "ping") {
        wsSend({ type: "pong" });
        return;
      }
      if (msg.type === "command" && msg.cmd) {
        var result = handleCommand(msg);
        wsSend({ type: "result", id: msg.id, result: result });
      }
    };
    ws.onclose = function () {
      log("WebSocket closed; reconnecting");
      ws = null;
      scheduleReconnect();
    };
    ws.onerror = function () {
      // onclose will follow; avoid noisy CSP spam logs
    };
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

  function waitDashboardThenExpose() {
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      if (window.Dashboard || tries > 60) {
        clearInterval(t);
        window.__ASTERISM_SHELL = {
          probe: runDashboardProbe,
          capture: captureOverlay,
          seedWorld: seedWorld,
          setPresentation: setPresentation,
          directRestore: directRestore,
          restoreViaHand: restoreViaHand,
          getLiveWorld: getLiveWorld,
          list: listAsterism,
          connectWs: connectWs,
        };
        if (DEBUG) log("Dashboard ready; WS bridge armed");
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
    waitDashboardThenExpose();
    connectWs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
