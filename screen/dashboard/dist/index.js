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
 * viewer id: the tab then shows "kendali dipegang sesi sebelumnya" and an
 * explicit Take over (last-writer-wins) or Hand back (Hermes's documented
 * release force:true for a lost viewer id) recovers it.
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
        const top = el.getBoundingClientRect().top;
        el.style.height = Math.max(240, Math.floor(window.innerHeight - top - 24)) + "px";
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
      } catch (e) { setErr("Take over gagal: " + apiErrorMessage(e)); }
      refreshLease();
    }
    async function handback() {
      setErr(null); setNote(null);
      try {
        const j = await SDK.fetchJSON(`${API}/lease/release`, { method: "POST" });
        applyLeaseResponse(j);
        if (j && j.forced) setNote("Kendali sesi sebelum restart sudah dikembalikan ke agen.");
      } catch (e) { setErr("Hand back gagal: " + apiErrorMessage(e)); }
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
        "Layar masih dipegang sesi sebelum dashboard restart. Klik Take over untuk ambil alih, atau Hand back untuk kembalikan ke agen.") : null,
      note ? h("div", { className: "hermes-screen-hint" }, note) : null,
      err ? h("div", { className: "hermes-screen-error" }, err) : null,
      h("div", { className: "hermes-screen-canvas", ref: screenRef,
                 "data-viewonly": lease !== "human" ? "true" : "false" }));
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("screen", ScreenPage);
  }
})();
