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

  var FIBER_WALK_MAX = 8000;

  function isUndockedLikeInstance(instance, targetFrameID) {
    if (!instance || typeof instance !== "object") return false;
    if (typeof instance.setState !== "function") return false;
    if (!instance.props || !instance.props.frame) return false;
    if (instance.props.frame.frameID == null) return false;
    if (String(instance.props.frame.frameID) !== String(targetFrameID)) return false;
    if (!instance.state || instance.state.xfTransform == null) return false;
    return true;
  }

  /** Weak identity: mounted class with matching frameID; xfTransform may be null. */
  function isWeakUndockedInstance(instance, targetFrameID) {
    if (!instance || typeof instance !== "object") return false;
    if (typeof instance.setState !== "function") return false;
    if (!instance.props || !instance.props.frame) return false;
    if (instance.props.frame.frameID == null) return false;
    return String(instance.props.frame.frameID) === String(targetFrameID);
  }

  function jsonSafePrimitive(v) {
    var t = typeof v;
    if (v === null || t === "string" || t === "boolean") return v;
    if (t === "number") return isFinite(v) ? v : null;
    return undefined;
  }

  function weakInstanceCandidateDiag(instance, tree) {
    // Read-only; never call component methods; never return the instance.
    var frameID = null;
    try {
      frameID =
        instance.props &&
        instance.props.frame &&
        instance.props.frame.frameID != null
          ? String(instance.props.frame.frameID)
          : null;
    } catch (_) {}
    var constructorName = null;
    try {
      constructorName =
        instance.constructor && instance.constructor.name
          ? String(instance.constructor.name)
          : null;
    } catch (_) {}
    var statePresent = false;
    var hasOwnXf = false;
    var xfNullish = true;
    var xfOut = undefined;
    var sParentDevice = undefined;
    var dragSnapLocation = undefined;
    try {
      statePresent = !!instance.state && typeof instance.state === "object";
      if (statePresent) {
        try {
          hasOwnXf = Object.prototype.hasOwnProperty.call(
            instance.state,
            "xfTransform"
          );
        } catch (_) {
          hasOwnXf = instance.state.xfTransform !== undefined;
        }
        var xf = instance.state.xfTransform;
        xfNullish = xf == null;
        if (!xfNullish) {
          var cloned = cloneTransform(xf);
          if (cloned) {
            try {
              JSON.stringify(cloned);
              xfOut = cloned;
            } catch (_) {}
          }
        }
        sParentDevice = jsonSafePrimitive(instance.state.sParentDevice);
        dragSnapLocation = jsonSafePrimitive(instance.state.dragSnapLocation);
      }
    } catch (_) {}
    var out = {
      tree: tree,
      frameID: frameID,
      constructorName: constructorName,
      hasSetState: typeof instance.setState === "function",
      statePresent: statePresent,
      hasOwnXfTransform: hasOwnXf,
      xfTransformNullish: xfNullish,
      sParentDevice: sParentDevice === undefined ? null : sParentDevice,
      dragSnapLocation:
        dragSnapLocation === undefined ? null : dragSnapLocation,
      hasSetInitialTransformForLocation:
        typeof instance.setInitialTransformForLocation === "function",
      hasComponentDidMount: typeof instance.componentDidMount === "function",
    };
    if (xfOut !== undefined) out.xfTransform = xfOut;
    return out;
  }

  /**
   * Bounded child/sibling walk; collects weak matches. Dedup via seenStateNodes.
   * Returns {matches:[{instance,snap}], visited}. Never serialize matches.instance.
   */
  function walkFiberTreeWeak(root, frameID, treeName, seenStateNodes) {
    var matches = [];
    var stack = root ? [root] : [];
    var visitedFibers = typeof Set !== "undefined" ? new Set() : null;
    var count = 0;
    while (stack.length && count < FIBER_WALK_MAX) {
      var fiber = stack.pop();
      if (!fiber || typeof fiber !== "object") continue;
      if (visitedFibers) {
        if (visitedFibers.has(fiber)) continue;
        visitedFibers.add(fiber);
      }
      count++;
      try {
        var sn = fiber.stateNode;
        if (isWeakUndockedInstance(sn, frameID)) {
          if (seenStateNodes && seenStateNodes.has(sn)) {
            // same instance already reported from the other tree
          } else {
            if (seenStateNodes) seenStateNodes.add(sn);
            matches.push({
              instance: sn,
              snap: weakInstanceCandidateDiag(sn, treeName),
            });
          }
        }
      } catch (_) {}
      try {
        if (fiber.child) stack.push(fiber.child);
        if (fiber.sibling) stack.push(fiber.sibling);
      } catch (_) {}
    }
    return { matches: matches, visited: count };
  }

  /**
   * Internal mounted-instance finder (weak identity). Searches primary then
   * alternate; may return instance with state.xfTransform == null.
   */
  function findMountedUndockedOverlayForFrame(frame) {
    var frameID = frame && frame.frameID != null ? String(frame.frameID) : null;
    var diag = {
      ok: false,
      frameID: frameID,
      found: false,
      identity: "weak",
      primaryVisited: 0,
      alternatePresent: false,
      alternateVisited: 0,
      xfTransformNullish: null,
    };
    if (!frameID) {
      diag.error = "no frameID";
      return { instance: null, diag: diag };
    }
    var dash = window.Dashboard;
    if (!dash || !dash._reactInternals) {
      diag.error = "Dashboard._reactInternals missing";
      return { instance: null, diag: diag };
    }
    var seen = typeof Set !== "undefined" ? new Set() : null;
    var primary = walkFiberTreeWeak(
      dash._reactInternals,
      frameID,
      "primary",
      seen
    );
    diag.primaryVisited = primary.visited;
    var altRoot = null;
    try {
      altRoot = dash._reactInternals.alternate;
    } catch (_) {}
    diag.alternatePresent = !!(altRoot && typeof altRoot === "object");
    var alternate = { matches: [], visited: 0 };
    if (diag.alternatePresent) {
      alternate = walkFiberTreeWeak(altRoot, frameID, "alternate", seen);
    }
    diag.alternateVisited = alternate.visited;
    var hit =
      (primary.matches && primary.matches[0]) ||
      (alternate.matches && alternate.matches[0]) ||
      null;
    if (!hit) {
      diag.error =
        primary.visited + alternate.visited >= FIBER_WALK_MAX
          ? "fiber cap reached"
          : "no matching mounted instance";
      return { instance: null, diag: diag };
    }
    var xfNullish = true;
    try {
      xfNullish =
        !hit.instance.state || hit.instance.state.xfTransform == null;
    } catch (_) {}
    diag.ok = true;
    diag.found = true;
    diag.tree = hit.snap && hit.snap.tree;
    diag.xfTransformNullish = xfNullish;
    diag.candidateCount = primary.matches.length + alternate.matches.length;
    return { instance: hit.instance, diag: diag };
  }

  /**
   * Read-only weak instance diagnostic: frameID match without requiring
   * xfTransform. Walks primary and alternate fiber roots separately.
   */
  function inspectUndockedInstance(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    var targetFrameID =
      frame && frame.frameID != null ? String(frame.frameID) : null;
    if (!targetFrameID) {
      return {
        ok: false,
        error: "no frame for overlay",
        targetFrameID: null,
        candidateCount: 0,
        primaryVisited: 0,
        alternatePresent: false,
        alternateVisited: 0,
        candidates: [],
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var dash = window.Dashboard;
    if (!dash || !dash._reactInternals) {
      return {
        ok: false,
        error: "Dashboard._reactInternals missing",
        targetFrameID: targetFrameID,
        candidateCount: 0,
        primaryVisited: 0,
        alternatePresent: false,
        alternateVisited: 0,
        candidates: [],
      };
    }
    var seen = typeof Set !== "undefined" ? new Set() : null;
    var primary = walkFiberTreeWeak(
      dash._reactInternals,
      targetFrameID,
      "primary",
      seen
    );
    var altRoot = null;
    try {
      altRoot = dash._reactInternals.alternate;
    } catch (_) {}
    var alternatePresent = !!(altRoot && typeof altRoot === "object");
    var alternate = { matches: [], visited: 0 };
    if (alternatePresent) {
      alternate = walkFiberTreeWeak(
        altRoot,
        targetFrameID,
        "alternate",
        seen
      );
    }
    var candidates = [];
    var i;
    for (i = 0; i < primary.matches.length; i++) {
      candidates.push(primary.matches[i].snap);
    }
    for (i = 0; i < alternate.matches.length; i++) {
      candidates.push(alternate.matches[i].snap);
    }
    return {
      ok: true,
      path: "react-fiber-weak",
      overlay_key: overlayKey,
      targetFrameID: targetFrameID,
      candidateCount: candidates.length,
      primaryVisited: primary.visited,
      alternatePresent: alternatePresent,
      alternateVisited: alternate.visited,
      candidates: candidates,
      note:
        "weak identity (setState+frameID); xfTransform may be null — Null xfTransform is not evidence of unmounted",
    };
  }

  /**
   * STRICT diagnostic finder: mounted weak instance AND non-null xfTransform.
   * find-live-uo keeps this meaning; direct-restore uses weak finder instead.
   */
  function findLiveUndockedOverlayForFrame(frame) {
    var mounted = findMountedUndockedOverlayForFrame(frame);
    var diag = {
      ok: false,
      frameID: mounted.diag.frameID,
      found: false,
      identity: "strict",
      visited:
        (mounted.diag.primaryVisited || 0) +
        (mounted.diag.alternateVisited || 0),
      primaryVisited: mounted.diag.primaryVisited,
      alternatePresent: mounted.diag.alternatePresent,
      alternateVisited: mounted.diag.alternateVisited,
      mountedWeak: !!(mounted.diag && mounted.diag.found),
      xfTransformNullish: mounted.diag.xfTransformNullish,
    };
    if (!mounted.instance) {
      diag.error = mounted.diag.error || "no matching live instance";
      return { instance: null, diag: diag };
    }
    var xf = null;
    try {
      xf = mounted.instance.state && mounted.instance.state.xfTransform;
    } catch (_) {}
    if (xf == null) {
      diag.error = "mounted but xfTransform nullish (strict find-live-uo)";
      diag.xfTransformNullish = true;
      return { instance: null, diag: diag };
    }
    // Keep isUndockedLikeInstance as the documented strict gate.
    if (!isUndockedLikeInstance(mounted.instance, mounted.diag.frameID)) {
      diag.error = "strict signature failed";
      return { instance: null, diag: diag };
    }
    diag.ok = true;
    diag.found = true;
    diag.tree = mounted.diag.tree;
    diag.signature = { hasSetState: true, hasXfTransform: true };
    return { instance: mounted.instance, diag: diag };
  }

  /** Safe static inspect — do not invoke render outside React. */
  function inspectRenderUndockedSafe() {
    var dash = window.Dashboard;
    var fn = dash && dash.renderUndockedLocalFrameTransforms;
    if (typeof fn !== "function") return { present: false };
    var src = "";
    try {
      src = Function.prototype.toString.call(fn);
    } catch (_) {}
    return {
      present: true,
      arity: fn.length,
      sourceLen: src.length,
      sourcePreview: src.slice(0, 480),
      mentionsXfTransform: src.indexOf("xfTransform") >= 0,
      mentionsCreateElement:
        src.indexOf("createElement") >= 0 || src.indexOf("jsx") >= 0,
      mentionsFrame: src.indexOf("frame") >= 0,
      knownSafeShape: renderUndockedSourceIsKnownSafe(src),
    };
  }

  /**
   * Only invoke renderUndockedLocalFrameTransforms when source matches the
   * known safe shape:
   *   frames_local_undocked.map(... createElement(..., {frame: ...}))
   */
  function renderUndockedSourceIsKnownSafe(src) {
    if (!src || typeof src !== "string") return false;
    return (
      src.indexOf("frames_local_undocked") >= 0 &&
      src.indexOf(".map") >= 0 &&
      src.indexOf("createElement") >= 0 &&
      src.indexOf("frame") >= 0
    );
  }

  function elementTypeDiag(el) {
    // Inert type metadata only — never invoke element.type / never serialize fibers.
    var out = {
      typeKind: null,
      typeName: null,
      typeDisplayName: null,
      typeSourceLength: null,
      typeSourcePreview: null,
      propsKeys: [],
      mentionsXfTransform: false,
      mentionsDockLocation: false,
      mentionsWorld: false,
      mentionsSetDockLocation: false,
      mentionsMapLastRelative: false,
      mentionsIsFullyVisible: false,
      mentionsShouldShowKeyboardHack: false,
    };
    try {
      var props = el && el.props;
      if (props && typeof props === "object") {
        try {
          out.propsKeys = Object.keys(props);
        } catch (_) {}
      }
      var t = el && el.type;
      out.typeKind = t === null ? "null" : typeof t;
      if (typeof t === "string") {
        out.typeName = t;
        out.typeDisplayName = t;
        return out;
      }
      if (typeof t === "function") {
        try {
          out.typeName = t.name ? String(t.name) : null;
        } catch (_) {}
        try {
          out.typeDisplayName =
            t.displayName != null
              ? String(t.displayName)
              : out.typeName;
        } catch (_) {
          out.typeDisplayName = out.typeName;
        }
        var src = "";
        try {
          src = Function.prototype.toString.call(t);
        } catch (_) {}
        out.typeSourceLength = src.length;
        out.typeSourcePreview = src.slice(0, 3000);
        out.mentionsXfTransform = src.indexOf("xfTransform") >= 0;
        out.mentionsDockLocation = src.indexOf("dockLocation") >= 0;
        out.mentionsWorld = src.indexOf("World") >= 0;
        out.mentionsSetDockLocation = src.indexOf("SetDockLocation") >= 0;
        out.mentionsMapLastRelative =
          src.indexOf("m_mapLastRelativeTransformForDockLocation") >= 0;
        out.mentionsIsFullyVisible = src.indexOf("isFullyVisible") >= 0;
        out.mentionsShouldShowKeyboardHack =
          src.indexOf("shouldShowKeyboardForUndockedFrame_Hack") >= 0;
        return out;
      }
      // object/symbol/etc — name only if cheap JSON-safe fields exist
      if (t && typeof t === "object") {
        try {
          if (t.displayName != null) out.typeDisplayName = String(t.displayName);
        } catch (_) {}
        try {
          if (t.name != null) out.typeName = String(t.name);
        } catch (_) {}
        if (!out.typeDisplayName) out.typeDisplayName = out.typeName;
      }
    } catch (_) {}
    return out;
  }

  function elementFrameDiag(el) {
    // Inert React element description only — never return the element itself.
    var typeSnap = elementTypeDiag(el);
    try {
      var props = el && el.props;
      var frame = props && props.frame;
      var keys = [];
      var summon = null;
      var frameID = null;
      if (frame) {
        try {
          keys = (frame.associatedSummonOverlayKeys || []).slice();
        } catch (_) {}
        try {
          summon = frame.activePage && frame.activePage.summonOverlayKey;
        } catch (_) {}
        try {
          frameID = frame.frameID != null ? String(frame.frameID) : null;
        } catch (_) {}
      }
      return {
        frameID: frameID,
        summonOverlayKey: summon,
        associatedSummonOverlayKeys: keys,
        typeKind: typeSnap.typeKind,
        typeName: typeSnap.typeName,
        typeDisplayName: typeSnap.typeDisplayName,
        typeSourceLength: typeSnap.typeSourceLength,
        typeSourcePreview: typeSnap.typeSourcePreview,
        propsKeys: typeSnap.propsKeys,
        mentionsXfTransform: typeSnap.mentionsXfTransform,
        mentionsDockLocation: typeSnap.mentionsDockLocation,
        mentionsWorld: typeSnap.mentionsWorld,
        mentionsSetDockLocation: typeSnap.mentionsSetDockLocation,
        mentionsMapLastRelative: typeSnap.mentionsMapLastRelative,
        mentionsIsFullyVisible: typeSnap.mentionsIsFullyVisible,
        mentionsShouldShowKeyboardHack: typeSnap.mentionsShouldShowKeyboardHack,
      };
    } catch (_) {
      return typeSnap;
    }
  }

  function inspectUndockedRender(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var dash = window.Dashboard;
    var fn = dash && dash.renderUndockedLocalFrameTransforms;
    if (typeof fn !== "function") {
      return {
        ok: false,
        error: "renderUndockedLocalFrameTransforms missing",
        count: 0,
        frames: [],
        targetFrameID: null,
        targetPresent: false,
      };
    }
    var src = "";
    try {
      src = Function.prototype.toString.call(fn);
    } catch (_) {}
    if (!renderUndockedSourceIsKnownSafe(src)) {
      return {
        ok: false,
        error: "renderUndockedLocalFrameTransforms source shape not recognized; refuse invoke",
        sourcePreview: src.slice(0, 240),
        count: 0,
        frames: [],
        targetFrameID: null,
        targetPresent: false,
      };
    }

    var resolved = resolveFrames(overlayKey);
    var target = resolved.frames && resolved.frames[0];
    var targetFrameID =
      target && target.frameID != null ? String(target.frameID) : null;

    var elements;
    try {
      elements = fn.call(dash);
    } catch (e) {
      return {
        ok: false,
        error: "renderUndockedLocalFrameTransforms threw: " + String(e),
        count: 0,
        frames: [],
        targetFrameID: targetFrameID,
        targetPresent: false,
      };
    }
    if (!Array.isArray(elements)) {
      return {
        ok: false,
        error: "renderUndockedLocalFrameTransforms did not return an array",
        returnType: elements === null ? "null" : typeof elements,
        count: 0,
        frames: [],
        targetFrameID: targetFrameID,
        targetPresent: false,
      };
    }

    var frames = [];
    var targetPresent = false;
    for (var i = 0; i < elements.length; i++) {
      var snap = elementFrameDiag(elements[i]);
      if (!snap) continue;
      frames.push(snap);
      if (
        targetFrameID != null &&
        snap.frameID != null &&
        String(snap.frameID) === String(targetFrameID)
      ) {
        targetPresent = true;
      }
    }
    return {
      ok: true,
      path: "renderUndockedLocalFrameTransforms",
      overlay_key: overlayKey,
      count: frames.length,
      frames: frames,
      targetFrameID: targetFrameID,
      targetPresent: targetPresent,
      note:
        "inert element+type metadata only (no invoke/mount); Case A if targetPresent&&!fiber, Case B if !targetPresent",
    };
  }

  function forceDashboardRender() {
    var dash = window.Dashboard;
    if (!dash || typeof dash.forceUpdate !== "function") {
      return {
        ok: false,
        error: "Dashboard.forceUpdate unavailable",
      };
    }
    try {
      dash.forceUpdate();
      return {
        ok: true,
        path: "Dashboard.forceUpdate",
        note: "diagnostic only; not wired into automatic persistence",
      };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }

  function findLiveDiag(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame) {
      return {
        ok: false,
        error: "no frame for overlay",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var found = findLiveUndockedOverlayForFrame(frame);
    return {
      ok: !!(found.diag && found.diag.found),
      path: "react-fiber",
      overlay_key: overlayKey,
      resolve_source: resolved.source,
      dockLocationName: ywqName(frame.docking && frame.docking.dockLocation),
      live: found.diag,
      renderUndocked: inspectRenderUndockedSafe(),
    };
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
    var dockTransformId = null;
    try {
      if (dock && typeof dock.GetDockLocationTransformID === "function") {
        dockTransformId = dock.GetDockLocationTransformID(dockLoc);
      }
    } catch (_) {}
    try {
      if (
        dockTransformId == null &&
        window.__ASTERISM_STEAMVR &&
        window.Dashboard &&
        typeof window.Dashboard.GetDockLocationTransformID === "function"
      ) {
        dockTransformId = window.Dashboard.GetDockLocationTransformID(dockLoc);
      }
    } catch (_) {}
    return {
      frameID: frame.frameID != null ? String(frame.frameID) : null,
      associatedSummonOverlayKeys: keys,
      summonOverlayKey: summon,
      dockLocation: dockLoc,
      dockLocationName: ywqName(dockLoc),
      rememberedTransforms: remembered,
      rememberedTransformKeys: Object.keys(remembered),
      dockLocationTransformID:
        dockTransformId != null ? String(dockTransformId) : null,
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

  function presentationToYwq(e, name) {
    var n = String(name || "").toLowerCase();
    if (!e) return null;
    if (n === "dashboard") return e.Dashboard;
    if (n === "world") return e.World;
    if (n === "theater") return e.Theater;
    if (n === "lefthand" || n === "left") return e.LeftHand;
    if (n === "righthand" || n === "right") return e.RightHand;
    return null;
  }

  function seedPresentationTransform(overlayKey, presentation, transform) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var e = ywq();
    if (!e) {
      return { ok: false, error: "yWq unavailable (need chunk bridge)" };
    }
    var loc = presentationToYwq(e, presentation);
    if (loc == null) {
      return {
        ok: false,
        error:
          "presentation must be dashboard|world|theater|lefthand|righthand",
      };
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
    map.set(loc, plain);
    return {
      ok: true,
      overlay_key: overlayKey,
      presentation: String(presentation || "").toLowerCase(),
      seeded: plain,
      after: frameSnapshot(frame),
    };
  }

  function seedWorld(overlayKey, transform) {
    return seedPresentationTransform(overlayKey, "world", transform);
  }

  function setPresentation(overlayKey, mode) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var e = ywq();
    var name = String(mode || "").toLowerCase();
    var loc = presentationToYwq(e, name);
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
    var plain = cloneTransform(transform);
    if (!plain) return { ok: false, error: "bad transform" };

    var e = ywq();
    if (!e || e.World == null) {
      return { ok: false, error: "yWq.World unavailable (need chunk bridge v1+)" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame || !frame.docking) {
      return {
        ok: false,
        error: "no frame/docking",
        resolve: resolveFramesReport(overlayKey),
        instanceFound: false,
      };
    }
    var dockLoc = frame.docking.dockLocation;
    if (dockLoc !== e.World) {
      return {
        ok: false,
        error: "dockLocation must be World for direct restore",
        dockLocationName: ywqName(dockLoc),
        path: "react-fiber-setState+map",
        instanceFound: false,
      };
    }

    // Weak mounted finder: xfTransform may still be null at cold World mount.
    var mounted = findMountedUndockedOverlayForFrame(frame);
    if (!mounted.instance) {
      return {
        ok: false,
        error: "no mounted UndockedOverlay instance via React fiber",
        path: "react-fiber-setState+map",
        instanceFound: false,
        liveInstanceFound: false,
        previousXfTransformNullish: null,
        initializedFromNull: false,
        live: mounted.diag,
      };
    }

    var previousXfTransformNullish = true;
    try {
      previousXfTransformNullish =
        !mounted.instance.state ||
        mounted.instance.state.xfTransform == null;
    } catch (_) {}

    var map = frame.docking.m_mapLastRelativeTransformForDockLocation;
    if (!map || typeof map.set !== "function") {
      return {
        ok: false,
        error: "map missing",
        path: "react-fiber-setState+map",
        instanceFound: true,
        previousXfTransformNullish: previousXfTransformNullish,
        initializedFromNull: false,
        live: mounted.diag,
      };
    }
    try {
      map.set(e.World, plain);
      mounted.instance.setState({ xfTransform: plain });
    } catch (err) {
      return {
        ok: false,
        error: String(err),
        path: "react-fiber-setState+map",
        instanceFound: true,
        previousXfTransformNullish: previousXfTransformNullish,
        initializedFromNull: false,
        live: mounted.diag,
      };
    }

    // Optional same-turn observe (setState may still be async).
    var postNullish = true;
    var postXf = null;
    try {
      postNullish =
        !mounted.instance.state ||
        mounted.instance.state.xfTransform == null;
      if (!postNullish) {
        postXf = cloneTransform(mounted.instance.state.xfTransform);
      }
    } catch (_) {}

    var snap = frameSnapshot(frame);
    return {
      ok: true,
      path: "react-fiber-setState+map",
      frameID: String(frame.frameID),
      dockLocationName: "World",
      instanceFound: true,
      liveInstanceFound: true,
      previousXfTransformNullish: previousXfTransformNullish,
      initializedFromNull: previousXfTransformNullish,
      postSetStateXfNullish: postNullish,
      postSetStateXf: postXf,
      live: mounted.diag,
      requested: plain,
      capture: snap,
      note:
        "weak-mounted init allowed; verify with get-live-world (strict) after React applies setState",
    };
  }

  function jsonSafeVec3(v) {
    if (v == null || typeof v !== "object") return null;
    try {
      var x = Number(v.x);
      var y = Number(v.y);
      var z = Number(v.z);
      if (!isFinite(x) || !isFinite(y) || !isFinite(z)) return null;
      return { x: x, y: y, z: z };
    } catch (_) {
      return null;
    }
  }

  /**
   * Read-only World float lifecycle + geometry inspect (no mutation).
   * Combines Frame docking fields with weak-mounted instance state.
   */
  function inspectWorldLifecycle(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frames = resolved.frames || [];
    if (frames.length !== 1) {
      return {
        ok: false,
        error:
          frames.length === 0
            ? "no frame for overlay"
            : "expected exactly one Frame, got " + frames.length,
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var frame = frames[0];
    if (!frame || !frame.docking) {
      return {
        ok: false,
        error: "frame.docking missing",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var justFloated = null;
    var isActive = null;
    var panelT = null;
    var scale = null;
    var beingDragged = null;
    try {
      if ("justFloatedFromDashboard" in frame.docking) {
        justFloated = !!frame.docking.justFloatedFromDashboard;
      }
    } catch (_) {}
    try {
      if ("isActiveDashboardFrame" in frame) {
        isActive = !!frame.isActiveDashboardFrame;
      }
    } catch (_) {}
    try {
      panelT = jsonSafeVec3(frame.docking.panelTranslationForResizeOrigin);
    } catch (_) {}
    try {
      if (frame.size && frame.size.scaleForActivePage != null) {
        var s = Number(frame.size.scaleForActivePage);
        scale = isFinite(s) ? s : null;
      }
    } catch (_) {}
    try {
      if ("beingDragged" in frame.docking) {
        beingDragged = !!frame.docking.beingDragged;
      }
    } catch (_) {}

    var mounted = findMountedUndockedOverlayForFrame(frame);
    var mountedWeak = !!(mounted.diag && mounted.diag.found);
    var xfNullish = null;
    var xfOut = undefined;
    if (mounted.instance) {
      try {
        xfNullish =
          !mounted.instance.state ||
          mounted.instance.state.xfTransform == null;
        if (!xfNullish) {
          var cloned = cloneTransform(mounted.instance.state.xfTransform);
          if (cloned) {
            try {
              JSON.stringify(cloned);
              xfOut = cloned;
            } catch (_) {}
          }
        }
      } catch (_) {
        xfNullish = null;
      }
    }

    var out = {
      ok: true,
      path: "inspect-world-lifecycle",
      frameID: frame.frameID != null ? String(frame.frameID) : null,
      dockLocationName: ywqName(frame.docking.dockLocation),
      justFloatedFromDashboard: justFloated,
      isActiveDashboardFrame: isActive,
      panelTranslationForResizeOrigin: panelT,
      scaleForActivePage: scale,
      beingDragged: beingDragged,
      mountedWeak: mountedWeak,
      xfTransformNullish: xfNullish,
    };
    if (xfOut !== undefined) out.xfTransform = xfOut;
    return out;
  }

  /** Read-only float-lifecycle flag inspect (no mutation). */
  function inspectJustFloated(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frames = resolved.frames || [];
    if (frames.length !== 1) {
      return {
        ok: false,
        error:
          frames.length === 0
            ? "no frame for overlay"
            : "expected exactly one Frame, got " + frames.length,
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var frame = frames[0];
    if (!frame || !frame.docking) {
      return {
        ok: false,
        error: "frame.docking missing",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var justFloated = null;
    var isActive = null;
    try {
      if ("justFloatedFromDashboard" in frame.docking) {
        justFloated = !!frame.docking.justFloatedFromDashboard;
      }
    } catch (_) {}
    try {
      if ("isActiveDashboardFrame" in frame) {
        isActive = !!frame.isActiveDashboardFrame;
      }
    } catch (_) {}
    return {
      ok: true,
      path: "inspect-just-floated",
      frameID: frame.frameID != null ? String(frame.frameID) : null,
      dockLocationName: ywqName(frame.docking.dockLocation),
      justFloatedFromDashboard: justFloated,
      isActiveDashboardFrame: isActive,
    };
  }

  /**
   * Clear justFloatedFromDashboard via SetJustFloatedFromDashboard(false).
   * Diagnostic generally; also used narrowly by exact World restore AFTER hide
   * + geometry settle to intentionally consume a stale cold-start float one-shot
   * (true→false triggers Valve's MobX nudge — expected before final restore).
   */
  function clearJustFloated(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frames = resolved.frames || [];
    if (frames.length !== 1) {
      return {
        ok: false,
        error:
          frames.length === 0
            ? "no frame for overlay"
            : "expected exactly one Frame, got " + frames.length,
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var frame = frames[0];
    if (!frame || !frame.docking) {
      return {
        ok: false,
        error: "frame.docking missing",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    if (typeof frame.docking.SetJustFloatedFromDashboard !== "function") {
      return {
        ok: false,
        error: "SetJustFloatedFromDashboard unavailable",
        frameID: frame.frameID != null ? String(frame.frameID) : null,
      };
    }
    var before = null;
    try {
      if ("justFloatedFromDashboard" in frame.docking) {
        before = !!frame.docking.justFloatedFromDashboard;
      }
    } catch (_) {
      before = null;
    }
    try {
      frame.docking.SetJustFloatedFromDashboard(false);
    } catch (err) {
      return {
        ok: false,
        error: String(err),
        frameID: frame.frameID != null ? String(frame.frameID) : null,
        before: before,
      };
    }
    var after = null;
    try {
      if ("justFloatedFromDashboard" in frame.docking) {
        after = !!frame.docking.justFloatedFromDashboard;
      }
    } catch (_) {
      after = null;
    }
    return {
      ok: true,
      path: "SetJustFloatedFromDashboard(false)",
      frameID: frame.frameID != null ? String(frame.frameID) : null,
      before: before,
      after: after,
      note:
        "true→false triggers Valve float nudge; exact World restore uses this only after hide+geometry settle",
    };
  }

  function getLiveWorld(overlayKey) {
    if (!looksAsterismKey(overlayKey)) {
      return { ok: false, error: "overlay key must start with asterism.desktop" };
    }
    var resolved = resolveFrames(overlayKey);
    var frame = resolved.frames && resolved.frames[0];
    if (!frame) {
      return {
        ok: false,
        error: "no frame for overlay",
        resolve: resolveFramesReport(overlayKey),
      };
    }
    var found = findLiveUndockedOverlayForFrame(frame);
    if (found.instance && found.instance.state && found.instance.state.xfTransform) {
      return {
        ok: true,
        path: "react-fiber",
        frameID: String(frame.frameID),
        dockLocation: frame.docking && frame.docking.dockLocation,
        dockLocationName: ywqName(frame.docking && frame.docking.dockLocation),
        xfTransform: cloneTransform(found.instance.state.xfTransform),
        live: found.diag,
      };
    }

    var bridge = window.__ASTERISM_STEAMVR;
    if (bridge && typeof bridge.getLiveWorldTransformForSummonKey === "function") {
      try {
        return bridge.getLiveWorldTransformForSummonKey(overlayKey);
      } catch (e) {
        return { ok: false, error: String(e), fiber: found.diag };
      }
    }
    return {
      ok: false,
      error: "no live xfTransform via React fiber",
      path: "react-fiber",
      live: found.diag,
      bridgeVersion: bridge && bridge.version,
    };
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
        "renderUndockedLocalFrameTransforms",
        "_reactInternals",
        "onGrabStart",
        "onGrabEnd",
      ];
      report.dashboardHas = {};
      for (var i = 0; i < interesting.length; i++) {
        var name = interesting[i];
        var has = false;
        try {
          has =
            typeof window.Dashboard[name] !== "undefined" ||
            (proto && proto.indexOf(name) >= 0);
        } catch (_) {}
        report.dashboardHas[name] = has;
      }
      report.hasReactInternals = !!window.Dashboard._reactInternals;
      report.renderUndocked = inspectRenderUndockedSafe();
      report.frameResolve = resolveFramesReport("asterism.desktop.app.2");
      report.bridgeVersion =
        window.__ASTERISM_STEAMVR && window.__ASTERISM_STEAMVR.version;
      report.liveUndocked = null;
      try {
        var rf = resolveFrames("asterism.desktop.app.2");
        if (rf.frames && rf.frames[0]) {
          report.liveUndocked = findLiveUndockedOverlayForFrame(rf.frames[0]).diag;
        }
      } catch (_) {}
      report.hasDirectApply = !!(
        (report.liveUndocked && report.liveUndocked.found) ||
        (window.__ASTERISM_STEAMVR &&
          typeof window.__ASTERISM_STEAMVR.applyWorldTransformForSummonKey ===
            "function")
      );
      report.directRestorePath = report.liveUndocked && report.liveUndocked.found
        ? "react-fiber-setState+map"
        : "unavailable";
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
      if (report.liveUndocked && report.liveUndocked.found) {
        report.notes.push(
          "live UndockedOverlay reachable via Dashboard._reactInternals fiber walk"
        );
      } else {
        report.notes.push(
          "live UndockedOverlay fiber lookup: " +
            ((report.liveUndocked && report.liveUndocked.error) || "not attempted")
        );
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
      else if (msg.cmd === "seed-presentation-transform")
        result = seedPresentationTransform(
          msg.overlay_key,
          msg.presentation,
          msg.transform
        );
      else if (msg.cmd === "set-presentation")
        result = setPresentation(msg.overlay_key, msg.mode);
      else if (msg.cmd === "direct-restore")
        result = directRestore(msg.overlay_key, msg.transform);
      else if (msg.cmd === "restore-via-hand")
        result = restoreViaHand(msg.overlay_key, msg.transform);
      else if (msg.cmd === "get-live-world")
        result = getLiveWorld(msg.overlay_key);
      else if (msg.cmd === "find-live-uo")
        result = findLiveDiag(msg.overlay_key);
      else if (msg.cmd === "inspect-undocked-render")
        result = inspectUndockedRender(msg.overlay_key);
      else if (msg.cmd === "inspect-undocked-instance")
        result = inspectUndockedInstance(msg.overlay_key);
      else if (msg.cmd === "inspect-world-lifecycle")
        result = inspectWorldLifecycle(msg.overlay_key);
      else if (msg.cmd === "inspect-just-floated")
        result = inspectJustFloated(msg.overlay_key);
      else if (msg.cmd === "clear-just-floated")
        result = clearJustFloated(msg.overlay_key);
      else if (msg.cmd === "force-dashboard-render")
        result = forceDashboardRender();
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
          seedPresentationTransform: seedPresentationTransform,
          setPresentation: setPresentation,
          directRestore: directRestore,
          restoreViaHand: restoreViaHand,
          getLiveWorld: getLiveWorld,
          findLiveUndocked: findLiveDiag,
          inspectUndockedRender: inspectUndockedRender,
          inspectUndockedInstance: inspectUndockedInstance,
          inspectWorldLifecycle: inspectWorldLifecycle,
          inspectJustFloated: inspectJustFloated,
          clearJustFloated: clearJustFloated,
          forceDashboardRender: forceDashboardRender,
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
