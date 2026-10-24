/**
 * Hermes Screen — Dashboard Plugin
 *
 * Live Bot Screen in a dashboard tab: noVNC view of the agent's virtual
 * desktop + Take over / Hand back. Backend: /api/plugins/screen/.
 * Plain IIFE, no build step; React via window.__HERMES_PLUGIN_SDK__.
 *
 * Semantics (pinned Hermes contract): refresh/reconnect is VIEW-ONLY — the
 * plugin never re-takes control automatically. A clean tab close while
 * holding the lease hands control back to the agent (Hermes bridge does
 * that itself); an abrupt drop keeps the human lease. If the dashboard
 * itself restarted mid-takeover, that kept lease is orphaned to a dead
 * viewer id. A foreign-held lease can ALSO be another live viewer (second
 * tab, Hermes Desktop, phone) - the plugin cannot tell those apart, so
 * recovery is always an explicit, effect-naming user action: Take over
 * (last-writer-wins) or the confirmed force hand-back (Hermes's documented
 * release force:true for a lost viewer id). A plain Hand back never
 * escalates on its own.
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const { React } = SDK;
  const h = React.createElement;
  const { Button } = SDK.components;
  const { useState, useEffect, useRef, useCallback } = SDK.hooks;

  const API = "/api/plugins/screen";
  const RFB_URL = "/dashboard-plugins/screen/dist/vendor/novnc/core/rfb.js";

  let rfbModule = null;
  async function loadRFB() {
    if (!rfbModule) rfbModule = await import(RFB_URL);
    return rfbModule.default;
  }

  function apiErrorMessage(err) {
    const raw = (err && err.message) ? String(err.message) : String(err || "");
    const m = raw.match(/^(\d{3}):\s*(.*)$/s);
    const body = m ? m[2] : raw;
    try {
      const parsed = JSON.parse(body);
      return parsed.hint || parsed.error || parsed.detail || raw;
    } catch (_e) { return body; }
  }

  function ScreenPage() {
    const screenRef = useRef(null);
    const rfbRef = useRef(null);
    const deadRef = useRef(false);
    const everConnected = useRef(false);
    const attempts = useRef(0);
    const pollRef = useRef(null);

    const [conn, setConn] = useState("memutuskan");
    const [lease, setLease] = useState("unknown");
    const [weHold, setWeHold] = useState(null);
    const [note, setNote] = useState(null);
    const [recovery, setRecovery] = useState(false);
    const [err, setErr] = useState(null);
    const [build, setBuild] = useState("");

    const refreshLease = useCallback(async function () {
      try {
        const j = await SDK.fetchJSON(`${API}/status`);
        const holder = (j.status && j.status.lease && j.status.lease.holder) || "unknown";
        setLease(holder);
        setWeHold(j.we_hold === true);
        if (rfbRef.current) rfbRef.current.viewOnly = holder !== "human";
      } catch (e) {
        setLease("error");
      }
    }, []);

    const connect = useCallback(async function () {
      if (deadRef.current) return;
      setConn("menyambung...");
      setErr(null);
      try {
        await SDK.fetchJSON(`${API}/observe`, { method: "POST" });
        const RFB = await loadRFB();
        const url = await SDK.buildWsUrl(`${API}/display/ws`, {});
        if (deadRef.current || !screenRef.current) return;
        if (rfbRef.current) { try { rfbRef.current.disconnect(); } catch (_e) {} }
        const rfb = new RFB(screenRef.current, url, {});
        rfb.viewOnly = true;
        rfb.scaleViewport = true;
        rfb.addEventListener("connect", function () {
          everConnected.current = true;
          attempts.current = 0;
          setConn("connected");
          refreshLease();
        });
        rfb.addEventListener("disconnect", function () {
          rfbRef.current = null;
          setConn("terputus");
          scheduleReconnect();
        });
        rfbRef.current = rfb;
      } catch (e) {
        setConn("gagal");
        setErr(apiErrorMessage(e));
        scheduleReconnect();
      }
    }, [refreshLease]);

    const scheduleReconnect = useCallback(function () {
      // Reconnect VIEW saja. Kendali tidak pernah diambil otomatis.
      if (!everConnected.current || deadRef.current) return;
      if (attempts.current >= 3) { setConn("terputus - klik Connect"); return; }
      attempts.current++;
      setConn("terputus, menyambung ulang (" + attempts.current + "/3)...");
      setTimeout(function () { if (!deadRef.current) connect(); }, 2000);
    }, [connect]);

    // Fit the canvas to the REAL leftover viewport: the dashboard's route
    // container gives plugins width but no height bound (App.tsx), so the
    // noVNC canvas (intrinsic 1440x900) stretched the page and made it
    // scroll. Measure the container's top against the window instead.
    useEffect(function () {
      function fit() {
        const el = screenRef.current;
        if (!el) return;
        // The real height bound is the dashboard's scroll container (MAIN,
        // overflow-y-auto), not the window: intermediate paddings (the plugin
        // page's own 16px and the route wrapper's 2rem) live below the canvas
        // inside that scroller. Size against it, then self-correct by the
        // measured leftover overflow so no magic number has to track Hermes
        // layout changes.
        let sc = el.parentElement;
        while (sc && sc !== document.body) {
          const oy = getComputedStyle(sc).overflowY;
          if (oy === "auto" || oy === "scroll") break;
          sc = sc.parentElement;
        }
        if (!sc || sc === document.body) sc = document.documentElement;
        const scRect = sc.getBoundingClientRect();
        const top = el.getBoundingClientRect().top - scRect.top + sc.scrollTop;
        const h = Math.max(240, Math.floor(sc.clientHeight - top - 8));
        el.style.height = h + "px";
        const over = sc.scrollHeight - sc.clientHeight;
        if (over > 0) el.style.height = Math.max(240, h - over) + "px";
      }
      fit();
      const t1 = setTimeout(fit, 300);
      const t2 = setTimeout(fit, 1500);
      window.addEventListener("resize", fit);
      return function () {
        clearTimeout(t1); clearTimeout(t2);
        window.removeEventListener("resize", fit);
      };
    }, []);

    // Mount: auto-connect view-only + poll lease; unmount: clean disconnect
    // (a clean close hands a held lease back to the agent — Hermes itself).
    useEffect(function () {
      deadRef.current = false;
      connect();
      SDK.fetchJSON(`${API}/build`).then(function (j) {
        if (j && j.build) setBuild(j.build);
      }).catch(function () {});
      pollRef.current = setInterval(refreshLease, 5000);
      return function () {
        deadRef.current = true;
        if (pollRef.current) clearInterval(pollRef.current);
        if (rfbRef.current) { try { rfbRef.current.disconnect(); } catch (_e) {} }
        rfbRef.current = null;
      };
    }, [connect, refreshLease]);

    function applyLeaseResponse(j) {
      const holder = (j && j.lease && j.lease.holder) || null;
      if (holder) setLease(holder);
      if (j && typeof j.we_hold === "boolean") setWeHold(j.we_hold);
      if (rfbRef.current && holder) rfbRef.current.viewOnly = holder !== "human";
    }
    async function takeover() {
      setErr(null); setNote(null);
      try {
        const j = await SDK.fetchJSON(`${API}/lease/acquire`, { method: "POST" });
        applyLeaseResponse(j);
        setRecovery(false);
      } catch (e) { setErr("Take over gagal: " + apiErrorMessage(e)); }
      refreshLease();
    }
    async function handback() {
      setErr(null); setNote(null);
      try {
        const j = await SDK.fetchJSON(`${API}/lease/release`, { method: "POST" });
        applyLeaseResponse(j);
        // Foreign holder (dead session OR another live viewer - we cannot
        // tell): only the explicit confirm below may escalate to force.
        setRecovery(j && j.recovery_required === true);
      } catch (e) { setErr("Hand back gagal: " + apiErrorMessage(e)); }
      refreshLease();
    }
    async function forceHandback() {
      setErr(null); setNote(null);
      try {
        const j = await SDK.fetchJSON(`${API}/lease/release`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: true }),
        });
        applyLeaseResponse(j);
        setRecovery(false);
        if (j && j.forced && j.holder === "agent") {
          setNote("Kendali sesi lain dilepas; layar kembali ke agen.");
        }
      } catch (e) { setErr("Lepas paksa gagal: " + apiErrorMessage(e)); }
      refreshLease();
    }

    const connected = conn === "connected";
    const orphaned = lease === "human" && weHold === false;
    return h("div", { className: "hermes-screen-page" },
      h("div", { className: "hermes-screen-toolbar" },
        h("span", {
          className: "hermes-screen-pill" + (connected ? " hermes-screen-pill--on" : ""),
          "data-conn": conn,
        }, conn),
        h("span", {
          className: "hermes-screen-pill" + (lease === "human" ? " hermes-screen-pill--warn" : ""),
          "data-lease": lease,
        }, "lease: " + lease),
        build ? h("span", { className: "hermes-screen-build" }, build) : null,
        h("div", { className: "hermes-screen-actions" },
          h(Button, { size: "sm", variant: "outline", onClick: connect, disabled: connected }, "Connect"),
          h(Button, { size: "sm", onClick: takeover,
                      disabled: !connected || (lease === "human" && weHold === true) }, "Take over"),
          h(Button, { size: "sm", variant: "outline", onClick: handback,
                      disabled: lease !== "human" }, "Hand back"))),
      orphaned ? h("div", { className: "hermes-screen-hint" },
        "Layar dipegang sesi lain: bisa sisa sesi sebelum dashboard restart, bisa perangkat lain yang sedang aktif. Take over mengambil alih dari sesi itu.") : null,
      recovery ? h("div", { className: "hermes-screen-hint" },
        "Hand back biasa tidak berpengaruh karena kendali dipegang sesi/perangkat lain. ",
        h("button", { className: "hermes-screen-forcelink", onClick: forceHandback },
          "Lepaskan kendali sesi itu ke agen")) : null,
      note ? h("div", { className: "hermes-screen-hint" }, note) : null,
      err ? h("div", { className: "hermes-screen-error" }, err) : null,
      h("div", { className: "hermes-screen-canvas", ref: screenRef,
                 "data-viewonly": lease !== "human" ? "true" : "false" }));
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("screen", ScreenPage);
  }
})();
