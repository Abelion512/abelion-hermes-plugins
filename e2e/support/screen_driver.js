// Drives the real Screen tab in real Chrome. Prints one JSON object of observations. No secrets.
const p = require('puppeteer-core');
const fs = require('fs');
const { execSync } = require('child_process');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const [url, chrome, marker, xauth, display] = process.argv.slice(2);
const sh = c => { try { return execSync(c, { stdio: 'pipe', env: { ...process.env, XAUTHORITY: xauth, DISPLAY: display } }).toString().trim(); } catch (e) { return ''; } };
(async () => {
  const b = await p.launch({ executablePath: chrome, headless: 'new', args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'] });
  const pg = await b.newPage(); await pg.setViewport({ width: 1440, height: 900 });
  const errs = [], httpErrors = [];
  pg.on('pageerror', e => errs.push(String(e)));
  pg.on('response', r => {
    const path = new URL(r.url()).pathname;
    if (r.status() >= 400 && (/\/api\/plugins\/screen\//.test(path) || /\/dashboard-plugins\/screen\//.test(path))) {
      httpErrors.push({ path, status: r.status() });
    }
  });
  await pg.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await sleep(3000);
  const out = { steps: {}, pageerrors: errs, http_errors: httpErrors };
  try {
    out.steps.api_build_probe = await pg.evaluate(async () => {
      const sdk = window.__HERMES_PLUGIN_SDK__;
      if (!sdk || typeof sdk.fetchJSON !== 'function') return { ok: false, message: 'plugin SDK unavailable' };
      try {
        const result = await sdk.fetchJSON('/api/plugins/screen/build');
        return { ok: true, build: result.build };
      } catch (e) {
        return { ok: false, message: String(e && e.message || e) };
      }
    });
  } catch (e) {
    out.steps.api_build_probe = { ok: false, message: String(e) };
  }
  const click = t => pg.evaluate(t => { const x = [...document.querySelectorAll('button')].find(b => b.textContent.trim().toLowerCase().startsWith(t)); if (x) x.click(); return !!x; }, t);
  const lease = () => pg.evaluate(() => { const m = document.body.innerText.match(/lease: (\w+)/); return m ? m[1] : null; });
  const typeIt = async name => {
    sh('xdotool search --onlyvisible --class xfce4-terminal windowfocus');
    const cv = await pg.$('canvas'); if (!cv) { out.steps.no_canvas_text = await pg.evaluate(() => document.body.innerText.slice(0, 600)); return false; }
    const bb = await cv.boundingBox();
    await pg.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2); await sleep(300);
    await pg.keyboard.type('touch ' + marker + name, { delay: 30 }); await pg.keyboard.press('Enter'); await sleep(1500);
    return fs.existsSync(marker + name);
  };
  out.steps.before_connect_text = await pg.evaluate(() => document.body.innerText.slice(0, 400));
  await click('connect'); await sleep(5000);
  out.steps.connected_lease = await lease();
  out.steps.typed_under_agent_lease = await typeIt('agent');
  await click('take over'); await sleep(2500);
  out.steps.takeover_lease = await lease();
  out.steps.typed_under_human_lease = await typeIt('human');
  await click('connect'); await sleep(3000);
  out.steps.reconnect_lease = await lease();
  out.steps.typed_after_reconnect = await typeIt('reconnect');
  await click('hand back'); await sleep(2500);
  out.steps.handback_lease = await lease();
  out.steps.typed_after_handback = await typeIt('handback');
  await b.close();
  console.log(JSON.stringify(out));
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
