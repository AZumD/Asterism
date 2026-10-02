# Bridge v2 black-rectangle analysis

**Date:** 2026-10-03  
**Broken staged SHA256:** `83a3bcbf43f179b290614af038835395226b0d8b54aaf188ce1a44c540a8aa2a`  
**Base v1 SHA256:** `272c1e40f75bafe28a7108485295681ffdac2a322a6a10f3e2d35278d596dfd9`

## Facts

- Giant black rectangle appeared **immediately after installing v2 and restarting SteamVR**.
- `direct-restore` was **never** called.
- Rolling chunk v2 → v1 removed the rectangle.
- New `d938425` shell + v1 chunk: **no** rectangle (shell isolated as innocent).

Therefore the fault is in the **Valve chunk v2 modifications at load/mount time**, not in shell `setState` usage.

## Exact v2 edits (three sites)

### 1) Bridge API (Dashboard `componentDidMount` chain)

Stock/v1 (expanded):

```js
window.Dashboard = this
window.__ASTERISM_STEAMVR || (window.__ASTERISM_STEAMVR = {
  version: 1,
  yWq: i.yWq,
  getFramesForSummonKey(e) {
    return M.JJ.GetFramesWithAssociatedSummonKeys(e) || []
  },
})
this.m_dashboardThumbnailsChangedEventHandle = …
```

v2 (expanded):

```js
window.__ASTERISM_STEAMVR = Object.assign(window.__ASTERISM_STEAMVR || {}, {
  version: 2,
  yWq: i.yWq,
  _uo: (window.__ASTERISM_STEAMVR && window.__ASTERISM_STEAMVR._uo) || {},
  getFramesForSummonKey(e) { … },
  applyWorldTransformForSummonKey(e, t) { … setState … },
  getLiveWorldTransformForSummonKey(e) { … },
})
```

### 2) UndockedOverlay `componentDidMount` (unconditional)

v2 injected (expanded):

```js
componentDidMount() {
  const e = this.props.frame
  var _A = (window.__ASTERISM_STEAMVR = window.__ASTERISM_STEAMVR || {})
  _A._uo = _A._uo || {}
  e && e.frameID != null && (_A._uo[e.frameID] = this)
  this.m_NudgeReactionHandle = … // original
}
```

Minified used a **comma-operator** chain into `this.m_NudgeReactionHandle=…`.

### 3) `componentWillUnmount` unregister

```js
try {
  var _f = this.props && this.props.frame
  var _A = window.__ASTERISM_STEAMVR
  if (_A && _A._uo && _f && _f.frameID != null && _A._uo[_f.frameID] === this)
    delete _A._uo[_f.frameID]
} catch (_e) {}
// then original reaction disposal
```

## Best-supported explanation (not proven root cause)

Most likely: **unconditional lifecycle instrumentation that retains every UndockedOverlay React instance in a global `_uo` map from first mount**.

Why this fits the evidence:

1. Failure at **load**, not on Asterism command → mount-time / render-tree effect.
2. UndockedOverlay backs **scene-graph** panels (`xfTransform` → compositor quads). Retaining / re-entering those instances incorrectly can produce a **fullscreen black quad**.
3. Registration was **not Asterism-gated** — SteamVR’s own undocked UI (including large/system surfaces) was eligible.
4. Mount rewrite also **eagerly creates** `window.__ASTERISM_STEAMVR = {}` if UndockedOverlay mounts before Dashboard finishes installing the v1/v2 API object (ordering hazard).
5. Comma-operator rewrite of `componentDidMount` is a secondary risk (expression semantics), but less specific than “all UO instances retained globally.”

Less likely without further A/B:

- Syntax error (chunk hashed/loaded; SteamVR ran enough to show a rectangle)
- `applyWorldTransform*` bodies (not invoked)
- Shell / CSP / WS (disproven by A/B)

**Not claimed as certainty.** Strongest next A/B if a Valve patch is ever needed again: mount-only Asterism-gated registration vs bridge-API-only vs full v2.

## Consequence

Prefer **zero additional Valve lifecycle patching**. Use `Dashboard._reactInternals` fiber walk from the shell on **v1**.

Broken v2 APPLY is now refused by the stage script. Contingency **v2.1** (Asterism-only register) is staged only if fiber fails live.
