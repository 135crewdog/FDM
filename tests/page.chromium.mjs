// Runs the built test page (test-page/, exactly the committed files) in headless Chromium, served under /FDM/
// like on GitHub Pages, and saves what the page printed. Chromium is not Safari: this shows the page works in a
// browser and in a real Web Worker; the iPhone result comes from the user.
//   node tests/page.chromium.mjs
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pageDir = join(root, "test-page");
const { chromium } = createRequire(import.meta.url)("playwright");
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm", ".json": "application/json", ".pack": "application/octet-stream", ".txt": "text/plain" };

const server = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  if (!url.pathname.startsWith("/FDM/")) { res.writeHead(404).end("not found"); return; }
  let file = normalize(join(pageDir, url.pathname.slice("/FDM/".length) || "index.html"));
  if (!file.startsWith(pageDir) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404).end("not found"); return; }
  res.writeHead(200, { "content-type": TYPES[extname(file)] ?? "application/octet-stream" }).end(readFileSync(file));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}/FDM/`;

const browser = await chromium.launch();
let failed = false;
const report = [];
async function run(label, url, before) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  if (before) { await page.goto(base + "build-id.txt"); await page.evaluate(before); }
  await page.goto(url);
  await page.waitForFunction(() => /\nDONE$/.test(document.getElementById("out").textContent), null, { timeout: 600000 });
  const text = await page.evaluate(() => document.getElementById("out").textContent);
  const status = await page.evaluate(() => document.getElementById("status").textContent);
  report.push(`##### ${label}: ${url.replace(base, "/FDM/")}`, text, `[status line: ${status}]`, `[browser console errors: ${consoleErrors.length}${consoleErrors.length ? ": " + consoleErrors.join(" | ") : ""}]`, "");
  await context.close();
  return { text, consoleErrors };
}

// 1. The default run: both builds.
const both = await run("both builds", base);
for (const need of ["-fwasm-exceptions: PASS", "-fexceptions: PASS", "uncaught errors: 0"]) {
  if (!both.text.includes(need)) { failed = true; console.log(`MISSING in the default run: ${need}`); }
}
if (both.consoleErrors.length) failed = true;
// 2. The fallback: a marker left by a load that died while starting -fwasm-exceptions.
const fallback = await run("fallback after a failed -fwasm-exceptions start", base, () => sessionStorage.setItem("fdm-starting", "weh"));
if (!/Running -fexceptions only \(fallback\)/.test(fallback.text) || !fallback.text.includes("-fexceptions: PASS") || fallback.text.includes("===== Build -fwasm-exceptions")) {
  failed = true;
  console.log("the fallback run did not behave as designed");
}
// 3. One build forced by the address.
const forced = await run("forced with ?build=weh", base + "?build=weh");
if (!forced.text.includes("-fwasm-exceptions: PASS") || forced.text.includes("===== Build -fexceptions")) { failed = true; console.log("?build=weh did not run only that build"); }

await browser.close();
server.close();
const version = `Chromium ${browser.version()} (headless), page build ${readFileSync(join(pageDir, "build-id.txt"), "utf8").trim()}`;
mkdirSync(join(root, "results"), { recursive: true });
writeFileSync(join(root, "results", "page-chromium.txt"), `${version}\n\n${report.join("\n")}\n${failed ? "CHROMIUM RUN: FAILED" : "CHROMIUM RUN: all three runs behaved as designed"}\n`);
console.log(version);
console.log(failed ? "FAILED" : "ok");
process.exit(failed ? 1 : 0);
