#!/usr/bin/env node
/* Headless test for cpd-console.html — drives the local Chromium headless
   shell over CDP (no jsdom on this box). Exercises: view navigation,
   on-screen disclosure, naive tamper test, bypass attempt, and the
   full-chain-rewrite vs. checkpoint scenario.
   Usage: node test-console.js [path-to-html] */
"use strict";
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");

const CHROME = "/home/hatch/.cache/ms-playwright/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell";
const HTML = process.argv[2] || "/home/hatch/workspace/noctua-sim/cpd-console.html";
const PORT = 9333;
const results = [];
let failures = 0;
function check(name, ok, extra) {
  results.push((ok ? "PASS" : "FAIL") + "  " + name + (extra ? "  — " + extra : ""));
  if (!ok) failures++;
}
function getJSON(path) {
  return new Promise((res, rej) => {
    http.get({ host: "127.0.0.1", port: PORT, path }, r => {
      let d = ""; r.on("data", c => d += c); r.on("end", () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } });
    }).on("error", rej);
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const proc = spawn(CHROME, ["--remote-debugging-port=" + PORT, "--no-sandbox",
    "--disable-dev-shm-usage", "--window-size=1400,1000",
    "--user-data-dir=/tmp/noctua-test-profile", "about:blank"],
    { stdio: ["ignore", "ignore", "pipe"] });
  let chromeErr = "";
  proc.stderr.on("data", d => chromeErr += d);
  try {
    // wait for the debug endpoint
    let targets = null;
    for (let i = 0; i < 50 && !targets; i++) {
      try { const t = await getJSON("/json/list"); if (t && t.length) targets = t; } catch (e) { /* not up yet */ }
      if (!targets) await sleep(200);
    }
    if (!targets) throw new Error("chromium debug endpoint never came up: " + chromeErr.slice(-400));
    const page = targets.find(t => t.type === "page") || targets[0];
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    let mid = 0; const pending = new Map(); const exceptions = [];
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id);
        m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); }
      else if (m.method === "Runtime.exceptionThrown") {
        exceptions.push(m.params.exceptionDetails.text + ": " +
          ((m.params.exceptionDetails.exception || {}).description || "").split("\n")[0]);
      }
    };
    const send = (method, params) => new Promise((res, rej) => {
      const id = ++mid; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params: params || {} }));
    });
    const ev = async expr => {
      const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
      if (r.exceptionDetails) throw new Error("eval failed: " + expr + " → " +
        ((r.exceptionDetails.exception || {}).description || r.exceptionDetails.text));
      return r.result.value;
    };
    const waitFor = async (desc, expr, timeout = 20000) => {
      const t0 = Date.now();
      while (Date.now() - t0 < timeout) { if (await ev(expr)) return true; await sleep(250); }
      throw new Error("timeout waiting for: " + desc);
    };
    await send("Page.enable"); await send("Runtime.enable");
    await send("Page.navigate", { url: "file://" + HTML });
    await waitFor("page scripts running", "typeof log !== 'undefined' && log.length >= 2");
    await waitFor("session-start checkpoint", "checkpoints.length >= 1");
    check("page loads, audit chain initialized", true, "entries=" + await ev("log.length"));

    // 1. disclosure line
    check("disclosure line present (.demo2)",
      await ev("!!document.querySelector('.demo2') && document.querySelector('.demo2').textContent.includes('simulates its backend') && document.querySelector('.demo2').textContent.includes('Janus API')"));

    // pause the live feed for determinism
    await ev("document.getElementById('runBtn').click()");

    // 2. navigate every view
    for (const v of ["ops", "hits", "search", "hotlist", "janus", "audit", "reports", "system"]) {
      await ev("document.querySelector('[data-view=\"" + v + "\"]').click()");
      check("view navigates: " + v, await ev("document.getElementById('view-" + v + "').classList.contains('on')"));
    }

    // 3. create QUERY entries via the Janus view (valid case)
    await ev("document.querySelector('[data-view=\"janus\"]').click()");
    await ev("document.getElementById('jCase').value='2027-1001'");
    await ev("document.getElementById('btnJanus').click()");
    await ev("document.getElementById('btnJanus').click()");
    await waitFor("QUERY entries in log", "log.filter(e=>e.kind==='QUERY').length >= 2");
    check("Janus queries logged", true);

    // 4. audit view: publish a checkpoint covering the current log
    await ev("document.querySelector('[data-view=\"audit\"]').click()");
    const cpBefore = await ev("checkpoints.length");
    await ev("document.getElementById('btnPublishCp').click()");
    await waitFor("manual checkpoint published", "checkpoints.length > " + cpBefore);
    check("checkpoint published (Clerk)", true, "checkpoints=" + await ev("checkpoints.length"));
    check("checkpoint table renders rows", await ev("document.querySelectorAll('#cpBody tr').length >= 1"));

    // 5. naive tamper test: verify fails, restore, verify passes
    await ev("document.getElementById('btnTamper').click()");
    await ev("document.getElementById('btnVerify2').click()");
    await waitFor("chain badge BROKEN after tamper",
      "document.getElementById('chainBadge').textContent.includes('BROKEN')");
    check("naive tamper → chain verify FAILS", true);
    await ev("document.getElementById('btnRestore').click()");
    await ev("document.getElementById('btnVerify2').click()");
    await waitFor("chain badge VERIFIED after restore",
      "document.getElementById('chainBadge').textContent.includes('VERIFIED')");
    check("restore → chain verify passes", true);

    // 6. bypass attempt
    await ev("document.getElementById('btnBypass').click()");
    await waitFor("BYPASS_ATTEMPT in audit table",
      "document.getElementById('auditBody').innerHTML.includes('BYPASS_ATTEMPT')", 15000);
    check("bypass attempt logged as BYPASS_ATTEMPT", true);
    check("bypass outcome message shown",
      await ev("document.getElementById('bypassOut').textContent.includes('logged')"));
    check("bypass shows no plate data",
      await ev("!document.querySelector('#bypassSteps .plate') && document.getElementById('bypassSteps').textContent.includes('no plate data returned')"));
    check("BYPASS_ATTEMPT attributed to current operator",
      await ev("log.some(e=>e.kind==='BYPASS_ATTEMPT' && e.fields.by==='det.okafor')"));

    // 7. full-chain rewrite: chain verify passes, checkpoint check fails
    await ev("document.getElementById('btnRewrite').click()");
    await waitFor("rewrite completes", "!document.getElementById('btnRestoreRewrite').disabled", 30000);
    check("full-chain rewrite executed", true);
    await ev("document.getElementById('btnVerify2').click()");
    await waitFor("chain badge VERIFIED on forged chain",
      "document.getElementById('chainBadge').textContent.includes('VERIFIED')");
    check("forged chain → plain chain verify PASSES (as designed)", true);
    await ev("document.getElementById('btnCheckCp').click()");
    await waitFor("checkpoint mismatch reported",
      "document.getElementById('rewriteOut').textContent.includes('CHECKPOINT MISMATCH')", 15000);
    check("forged chain → checkpoint check FAILS (caught by outside witness)", true);

    // 8. restore: both checks pass again
    await ev("document.getElementById('btnRestoreRewrite').click()");
    await waitFor("restore completes", "!document.getElementById('btnRewrite').disabled", 30000);
    await ev("document.getElementById('btnVerify2').click()");
    await waitFor("chain badge VERIFIED after rewrite-restore",
      "document.getElementById('chainBadge').textContent.includes('VERIFIED')");
    check("rewrite restore → chain verify passes", true);
    await ev("document.getElementById('btnCheckCp').click()");
    await waitFor("checkpoints match after restore",
      "document.getElementById('rewriteOut').textContent.includes('CHECKPOINTS MATCH')", 15000);
    check("rewrite restore → checkpoint check passes", true);

    check("no uncaught page exceptions", exceptions.length === 0, exceptions.join(" | ").slice(0, 300));
    ws.close();
  } catch (e) {
    check("harness completed", false, e.message);
  } finally {
    proc.kill("SIGKILL");
  }
  console.log(results.join("\n"));
  console.log(failures ? "\n" + failures + " FAILURE(S)" : "\nALL CHECKS PASSED");
  process.exit(failures ? 1 : 0);
})();
