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

    const [zoom, setZoom] = useState(function () {
      try { return localStorage.getItem("hermes-screen-zoom") === "100" ? "100" : "fit"; }
      catch (_e) { return "fit"; }
    });
    const zoomRef = useRef(zoom);
    const [isFs, setIsFs] = useState(false);
    function applyZoom(rfb, z, viewOnly) {
      // fit: noVNC scales the remote into the container. 100%: no scaling
      // and NO clipViewport - the canvas keeps the full remote size and the
      // viewer's own overflow:auto div gives native scroll/wheel panning
      // (clipViewport instead crops to a window you can only drag-pan).
      // Pointer mapping stays correct: noVNC maps through the canvas's
      // (scrolled) bounding rect.
      if (!rfb) return;
      rfb.scaleViewport = z === "fit";
      rfb.clipViewport = false;
      rfb.dragViewport = false;
    }

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
        applyZoom(rfb, zoomRef.current, true);
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

    function closeReasonText(c) {
      if (!c) return null;
      if (c.code === 4401) return "sesi display kedaluwarsa/dipakai - mencoba lagi";
      if (c.code === 4409) return "sesi display belum siap - mencoba lagi";
      if (c.code === 4000) return "kendali diambil sesi lain";
      if (c.code === 4001) return "Bot Desktop tidak sedang berjalan";
      if (c.code === 1011) return "jembatan display tidak terjangkau";
      return null;
    }

    const scheduleReconnect = useCallback(function () {
      // Reconnect VIEW saja. Kendali tidak pernah diambil otomatis.
      // Berlaku juga sebelum connect pertama: refresh yang kalah balapan
      // tiket (tab lain / refresh ganda) atau load pertama yang lambat
      // harus pulih sendiri, bukan diam di layar hitam.
      if (deadRef.current) return;
      if (attempts.current >= 3) { setConn("terputus - klik Connect"); return; }
      attempts.current++;
      setConn("terputus, menyambung ulang (" + attempts.current + "/3)...");
      // Tanyakan penyebab putus terakhir (kode+alasan saja, tanpa rahasia)
      // supaya tab bisa bilang KENAPA, bukan cuma hitam.
      SDK.fetchJSON(`${API}/display/last_close`).then(function (j) {
        const t = j && j.last_close && closeReasonText(j.last_close);
        if (t) setNote(t);
      }).catch(function () {});
      setTimeout(function () { if (!deadRef.current) connect(); }, 2000);
    }, [connect]);

    // Edge-to-edge layout: the shell wraps plugin routes in a padded column
    // (App.tsx: px-3 sm:px-6, pt-2/4/6, pb-8 + the route wrapper's pb). We
    // NEGATE those paddings with measured negative margins so the desktop
    // touches the sidebar, the page header, and the browser's right/bottom
    // edges - plugin-owned CSS only, no shell edit. Paddings are MEASURED at
    // runtime (not hardcoded), so shell spacing changes can't silently break
    // the flush. Height = the column's full clientHeight; the parent's
    // padding-bottom is cancelled by the negative margin-bottom, so the route
    // gains no scrollbar.
    const pageRef = useRef(null);
    function layoutFlush() {
      const el = pageRef.current;
      if (!el) return;
      if (document.fullscreenElement === el) return; // CSS :fullscreen owns sizing
      // Find the route's scroll container (MAIN overflow-y-auto) and sum the
      // paddings of every ancestor between the plugin and it. Negating those
      // with margins makes the desktop touch the sidebar, the page header and
      // the browser's right/bottom edges; height = the scroller's client box.
      // The bottom margin also swallows the TOP reclaim so the parent chain's
      // box never exceeds the scroller and the route gains no scrollbar.
      let sc = el.parentElement;
      while (sc && sc !== document.body) {
        const oy = getComputedStyle(sc).overflowY;
        if (oy === "auto" || oy === "scroll") break;
        sc = sc.parentElement;
      }
      if (!sc || sc === document.body) sc = document.documentElement;
      // Rect-based flush: exact even when the scroller reserves a scrollbar
      // gutter (clientWidth math with paddings undershoots by the gutter).
      if (sc.clientHeight < 200) return; // unexpected host: graceful default
      const sr = sc.getBoundingClientRect();
      let r = el.getBoundingClientRect();
      const pc = getComputedStyle(el);
      const num = function (v) { const n = parseFloat(v); return isFinite(n) ? n : 0; };
      el.style.marginLeft = num(pc.marginLeft) + (sr.left - r.left) + "px";
      el.style.marginRight = "0px";
      el.style.marginTop = num(pc.marginTop) + (sr.top - r.top) + "px";
      el.style.marginBottom = "0px";
      r = el.getBoundingClientRect(); // forced reflow: margins applied
      el.style.width = Math.max(0, Math.floor(sr.left + sc.clientWidth - r.left)) + "px";
      el.style.height = Math.max(0, Math.floor(sr.top + sc.clientHeight - r.top)) + "px";
    }

    // Zoom: "fit" shrinks the whole desktop into view (default; small text on
    // big remote resolutions); "100%" shows real pixels with pan (drag in view
    // mode, scrollbars otherwise). Fullscreen gives the fit mode the whole
    // display. Input coordinates stay correct in both: noVNC maps pointer
    // position through its own transform.
    useEffect(function () {
      zoomRef.current = zoom;
      try { localStorage.setItem("hermes-screen-zoom", zoom); } catch (_e) {}
      const el = screenRef.current;
      if (el) el.classList.toggle("hermes-screen-canvas--clip", zoom === "100");
      applyZoom(rfbRef.current, zoom, lease !== "human");
    }, [zoom, lease]);
    // Sidebar collapse/expand, window resizes and shell reflows change the
    // padded column's box; re-measure so the flush stays pixel-exact. noVNC's
    // own ResizeObserver re-scales the remote to the canvas for fit mode.
    useEffect(function () {
      const el = pageRef.current;
      if (!el || typeof ResizeObserver === "undefined") return;
      const ro = new ResizeObserver(function () { layoutFlush(); });
      if (el.parentElement && el.parentElement.parentElement) {
        ro.observe(el.parentElement.parentElement);
      }
      window.addEventListener("resize", layoutFlush);
      return function () {
        ro.disconnect();
        window.removeEventListener("resize", layoutFlush);
      };
    }, []);
    function toggleFullscreen() {
      const el = pageRef.current;
      if (!el) return;
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(function () {});
      } else if (el.requestFullscreen) {
        // Surface a rejection instead of failing silently: on a phone the
        // reason (gesture, permission, unsupported) is the only feedback.
        const p = el.requestFullscreen();
        if (p && p.catch) p.catch(function (e) {
          setErr("Layar penuh gagal: " + ((e && e.message) || e));
        });
      } else {
        setErr("Layar penuh tidak didukung browser ini.");
      }
    }
    useEffect(function () {
      function onFs() { setIsFs(!!document.fullscreenElement); }
      document.addEventListener("fullscreenchange", onFs);
      document.addEventListener("fullscreenerror", onFs);
      return function () {
        document.removeEventListener("fullscreenchange", onFs);
        document.removeEventListener("fullscreenerror", onFs);
      };
    }, []);

    useEffect(function () {
      layoutFlush();
      const t1 = setTimeout(layoutFlush, 300);
      const t2 = setTimeout(layoutFlush, 1500);
      return function () { clearTimeout(t1); clearTimeout(t2); };
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
    const overlay =
      orphaned || recovery || note || err
        ? h("div", { className: "hermes-screen-overlay" },
            orphaned ? h("div", { className: "hermes-screen-hint" },
              "Layar dipegang sesi lain: bisa sisa sesi sebelum dashboard restart, bisa perangkat lain yang sedang aktif. Take over mengambil alih dari sesi itu.") : null,
            recovery ? h("div", { className: "hermes-screen-hint" },
              "Hand back biasa tidak berpengaruh karena kendali dipegang sesi/perangkat lain. ",
              h("button", { className: "hermes-screen-forcelink", onClick: forceHandback },
                "Lepaskan kendali sesi itu ke agen")) : null,
            note ? h("div", { className: "hermes-screen-hint" }, note) : null,
            err ? h("div", { className: "hermes-screen-error" }, err) : null)
        : null;
    return h("div", { className: "hermes-screen-page", ref: pageRef },
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
          h(Button, { size: "sm", variant: "outline",
                      onClick: function () { setZoom(zoom === "100" ? "fit" : "100"); } },
            zoom === "100" ? "Zoom: 100%" : "Zoom: pas"),
          h(Button, { size: "sm", variant: "outline", onClick: toggleFullscreen },
            isFs ? "Tutup layar penuh" : "Layar penuh"),
          h(Button, { size: "sm", variant: "outline", onClick: connect, disabled: connected }, "Connect"),
          h(Button, { size: "sm", onClick: takeover,
                      disabled: !connected || (lease === "human" && weHold === true) }, "Take over"),
          h(Button, { size: "sm", variant: "outline", onClick: handback,
                      disabled: lease !== "human" }, "Hand back"))),
      h("div", { className: "hermes-screen-stage" },
        h("div", { className: "hermes-screen-canvas", ref: screenRef,
                   "data-viewonly": lease !== "human" ? "true" : "false" }),
        overlay));
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("screen", ScreenPage);
  }
})();
