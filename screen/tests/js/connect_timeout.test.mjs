// Regression: a connect() cycle whose RFB never fires "connect"/"disconnect"
// (stalled WS upgrade or handshake) must NOT leave the tab on "menyambung..."
// with a disabled Connect button forever. Dependency-free: tiny hooks runtime,
// the REAL dashboard/dist/index.js, mocked SDK + noVNC. Run: node connect_timeout.test.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.join(here, "..", "..", "dashboard", "dist", "index.js"), "utf8");
const T = 120; // test timeout (shipping value is 15000)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const text = (n) => (n == null || n === false ? "" : typeof n === "string" ? n :
  Array.isArray(n) ? n.map(text).join("|") : text(n.children));

function mount(opts) {
  const calls = [];
  let rfbCount = 0, rfbDisconnects = 0;
  const rfbs = [];
  const mode = opts.rfb || "never"; // never | ok
  class RFB {
    constructor() { rfbCount++; this.l = {}; rfbs.push(this);
      if (mode === "ok") setTimeout(() => this.l.connect && this.l.connect(), 10); }
    addEventListener(e, f) { this.l[e] = f; }
    disconnect() { rfbDisconnects++; }
  }
  // --- minimal hooks runtime
  let hooks = [], idx = 0, effects = [], dirty = false, alive = true, Comp = null, tree = null;
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const render = () => { dirty = false; idx = 0; effects = []; tree = Comp(); flush(); };
  const flush = () => { for (const [i, fn, deps] of effects) {
      const h = hooks[i]; if (h.deps && same(h.deps, deps)) continue;
      if (h.cleanup) h.cleanup(); h.deps = deps; h.cleanup = fn() || null; } };
  const schedule = () => { if (!dirty && alive) { dirty = true; queueMicrotask(() => alive && render()); } };
  const useState = (init) => { const i = idx++; if (!hooks[i]) hooks[i] = { v: typeof init === "function" ? init() : init };
    const h = hooks[i]; return [h.v, (v) => { const nv = typeof v === "function" ? v(h.v) : v; if (nv !== h.v) { h.v = nv; schedule(); } }]; };
  const useRef = (init) => { const i = idx++; if (!hooks[i]) hooks[i] = { v: { current: init } }; return hooks[i].v; };
  const useEffect = (fn, deps) => { const i = idx++; if (!hooks[i]) hooks[i] = {}; effects.push([i, fn, deps]); };
  const useCallback = (fn, deps) => { const i = idx++; if (!hooks[i]) hooks[i] = {};
    const h = hooks[i]; if (!h.deps || !same(h.deps, deps)) { h.deps = deps; h.fn = fn; } return h.fn; };
  const createElement = (type, props, ...children) => {
    if (typeof type === "function") return type({ ...(props || {}), children: children.length === 1 ? children[0] : children });
    return { type, props: props || {}, children: children.flat(Infinity) }; };
  const win = {
    __HERMES_PLUGIN_SDK__: {
      React: { createElement }, hooks: { useState, useRef, useEffect, useCallback },
      components: { Button: (p) => createElement("button", { onClick: p.onClick, disabled: p.disabled }, p.children) },
      fetchJSON: async (u, o) => { calls.push((o && o.method || "GET") + " " + u);
        if (opts.observeDelay && u.endsWith("/observe")) await sleep(opts.observeDelay);
        if (opts.statusBody && u.endsWith("/status")) return opts.statusBody;
        return { ok: true, build: "t", status: { lease: { holder: "agent" } }, lease: { holder: "agent" }, last_close: null }; },
      buildWsUrl: async () => "ws://mock/x",
    },
    __HERMES_PLUGINS__: { register: (n, c) => { Comp = c; } },
    __rfbMod: opts.novncHang ? new Promise(() => {}) : { default: RFB },
  };
  const g = { window: win, document: { fullscreenElement: null, addEventListener() {}, removeEventListener() {},
      querySelectorAll() { return []; }, querySelector() { return null; }, body: {}, documentElement: { clientHeight: 0 } },
    localStorage: { getItem() { return null; }, setItem() {} }, getComputedStyle: () => ({}),
    MutationObserver: class { observe() {} disconnect() {} }, ResizeObserver: class { observe() {} disconnect() {} },
    addEventListener() {}, removeEventListener() {}, setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask, console, Promise };
  g.globalThis = g; g.window.window = win;
  const code = SRC.replace("await import(RFB_URL)", "await window.__rfbMod")
                  .replace(/CONNECT_TIMEOUT_MS = \d+/, "CONNECT_TIMEOUT_MS = " + T);
  if (!/CONNECT_TIMEOUT_MS = \d+/.test(SRC)) opts.noTimeoutConst = true;
  vm.runInNewContext(code, g);
  // refs: screenRef needs a node with textContent / classList
  const origUseRef = useRef;
  render();
  // attach fake DOM node to the screen ref (first useRef) so connect() proceeds
  hooks.forEach((h) => { if (h.v && h.v.current === null) h.v.current = { classList: { toggle() {} }, style: {}, textContent: "" }; });
  render();
  return {
    calls, get rfbCount() { return rfbCount; }, get rfbDisconnects() { return rfbDisconnects; }, rfbs,
    pill: () => text(tree), connectDisabled: () => { const find = (n) => !n || typeof n === "string" ? null :
      Array.isArray(n) ? n.map(find).find(Boolean) : (n.type === "button" && n.children[0] === "Connect") ? n : find(n.children);
      const b = find(tree); return b && b.props.disabled; },
    unmount: () => { alive = false; hooks.forEach((h) => h.cleanup && h.cleanup()); },
  };
}

let failed = 0;
const check = (name, ok, extra) => { console.log((ok ? "PASS " : "FAIL ") + name + (ok ? "" : "  -> " + extra)); if (!ok) failed++; };

// 1. stalled RFB: must leave "menyambung..." and re-enable Connect (this is the lock).
{ const m = mount({ rfb: "never" }); await sleep(30);
  check("starts connecting", /menyambung\.\.\./.test(m.pill()) && m.connectDisabled() === true, m.pill());
  await sleep(T + 60);
  check("stall ends: not stuck on menyambung...", !/\|menyambung\.\.\.\|/.test("|" + m.pill() + "|") && m.connectDisabled() === false, m.pill() + " disabled=" + m.connectDisabled());
  check("stage named (handshake RFB)", /handshake layar \(RFB\)/.test(m.pill()), m.pill());
  check("one RFB per cycle, no parallel cycles", m.rfbCount === 1, "rfbCount=" + m.rfbCount);
  check("stalled RFB was disconnected", m.rfbDisconnects >= 1, "disconnects=" + m.rfbDisconnects);
  await sleep(2200 + T * 3); // auto retries (2s apart) run out
  const p = m.pill();
  check("retries exhaust to manual 'klik Connect'", m.rfbCount <= 4 && m.connectDisabled() === false, p + " rfb=" + m.rfbCount);
  check("never takes control by itself", !m.calls.some((c) => /lease|takeover|handback/i.test(c)), m.calls.join(","));
  m.unmount(); const n = m.rfbCount; await sleep(2500 + T);
  check("unmount: no further connect cycles", m.rfbCount === n, "rfb " + n + " -> " + m.rfbCount); }

// 2. healthy connect is untouched by the timer.
{ const m = mount({ rfb: "ok" }); await sleep(T * 3);
  check("healthy: stays connected past timeout", /connected/.test(m.pill()) && m.rfbCount === 1 && m.rfbDisconnects === 0, m.pill() + " rfb=" + m.rfbCount); m.unmount(); }

// 3. hang BEFORE rfb (noVNC module never loads): bounded too, stage named, no RFB made.
{ const m = mount({ novncHang: true }); await sleep(T + 80);
  check("noVNC load stall is bounded and named", /muat noVNC/.test(m.pill()) && m.connectDisabled() === false && m.rfbCount === 0, m.pill()); m.unmount(); }

// 4. late await of an aborted cycle must not create a stale RFB.
{ const m = mount({ rfb: "never", observeDelay: T * 3 }); await sleep(T + 60);
  check("slow /observe stall is bounded", m.connectDisabled() === false, m.pill());
  await sleep(T * 4);
  check("late observe of aborted cycle creates no stale RFB", m.rfbCount <= 1, "rfbCount=" + m.rfbCount); m.unmount(); }

if (failed) { console.log(failed + " failed"); process.exit(1); }
console.log("all passed");
