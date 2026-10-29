#!/usr/bin/env node
/**
 * SportCam docs viewer — zero-dependency.
 *
 *   npm run docs        (or: node tools/docs-server.mjs)
 *   → http://localhost:8090
 *
 * Serves the repo statically and renders the markdown docs in a browser with
 * a sidebar, working images, .md cross-links, a With UWB / Without UWB
 * toggle that shows one build's docs at a time (tools/docs-viewer.js says
 * what it hides), and a Full build / Bench test switch that swaps each
 * build's setup docs for its bench rig's (docs/<build>/bench/). Markdown is
 * rendered client-side with marked, vendored in
 * tools/vendor/ so the viewer works offline (re-fetch with
 * tools/update-vendor.sh to upgrade).
 */
import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { join, normalize, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = normalize(join(dirname(fileURLToPath(import.meta.url)), ".."));
const PORT = Number(process.env.DOCS_PORT ?? 8090);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".stl": "model/stl",
  ".scad": "text/plain; charset=utf-8",
  ".py": "text/plain; charset=utf-8",
  ".ts": "text/plain; charset=utf-8",
  ".ino": "text/plain; charset=utf-8",
};

const PAGE = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SportCam docs</title>
<script src="/tools/vendor/marked.min.js"></script>
<style>
  :root { --bg:#0d1420; --panel:#131c2c; --ink:#e8edf6; --muted:#7f8ea8; --acc:#2f6fed; --border:#243247; }
  * { box-sizing:border-box; }
  body { margin:0; display:flex; min-height:100vh; background:var(--bg); color:var(--ink);
         font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif; }
  nav { width:270px; flex:none; background:var(--panel); border-right:1px solid var(--border);
        padding:18px 14px; position:sticky; top:0; height:100vh; overflow-y:auto; }
  nav h1 { font-size:15px; margin:0 0 12px; color:var(--acc); }
  nav a { display:block; color:var(--ink); text-decoration:none; padding:7px 10px; border-radius:8px;
          font-size:13.5px; margin-bottom:2px; }
  nav a:hover { background:#1b2740; }
  nav h2 { font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
           margin:16px 10px 6px; }
  nav a.active { background:var(--acc); color:#fff; }
  main { flex:1; min-width:0; padding:32px 40px 80px; max-width:900px; }
  main img { max-width:100%; border-radius:8px; background:#fff; }
  main h1,h2,h3 { line-height:1.3; }
  main h1 { border-bottom:1px solid var(--border); padding-bottom:8px; }
  main a { color:var(--acc); }
  main code { background:#1b2740; padding:2px 5px; border-radius:5px; font-size:0.9em; }
  main pre { background:#0a101b; border:1px solid var(--border); padding:14px; border-radius:10px;
             overflow-x:auto; }
  main pre code { background:none; padding:0; }
  main table { border-collapse:collapse; width:100%; font-size:14px; display:block; overflow-x:auto; }
  main th, main td { border:1px solid var(--border); padding:7px 10px; text-align:left; vertical-align:top; }
  main th { background:var(--panel); }
  main blockquote { border-left:3px solid var(--acc); margin:0; padding:2px 16px; color:var(--muted); }
  .err { color:#d64541; }
  .build-label { font-size:11.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted);
                 margin:0 10px 6px; }
  .toggle { display:flex; gap:2px; padding:3px; margin-bottom:6px; background:var(--bg);
            border:1px solid var(--border); border-radius:10px; }
  .toggle button { flex:1; border:0; border-radius:7px; padding:7px 4px; background:none; color:var(--muted);
                   font:600 13px/1.2 inherit; font-family:inherit; cursor:pointer; }
  .toggle button:hover { color:var(--ink); }
  .toggle button[aria-pressed="true"] { background:var(--acc); color:#fff; }
  .toggle button:focus-visible { outline:2px solid var(--acc); outline-offset:2px; }
</style>
</head>
<body>
<nav>
  <h1>📷 SportCam</h1>
  <div class="build-label" id="build-label">Showing the build</div>
  <div id="build-toggle" class="toggle" role="group" aria-labelledby="build-label"></div>
  <div id="bench-toggle" class="toggle" role="group" aria-label="Full build or bench test"></div>
  <div id="toc">loading…</div>
</nav>
<main id="content"></main>
<script src="/tools/docs-viewer.js"></script>
</body>
</html>`;

// Every .md in `dir` (if it exists), titled by its first heading. `build`
// tags a build's own docs, so the viewer's toggle can show one build at a
// time; `kind` marks the full build's setup docs ("setup") and the bench
// rig's ("bench"), which the viewer's bench switch swaps between.
async function mdEntries(dir, build = null, kind = null) {
  let files;
  try {
    files = (await readdir(join(ROOT, dir))).filter((f) => f.endsWith(".md") && f !== "README.md");
  } catch {
    return [];
  }
  const out = [];
  for (const f of files) {
    const first = (await readFile(join(ROOT, dir, f), "utf8")).split("\n")[0];
    const path = `${dir}/${f}`;
    out.push({ path, title: first.replace(/^#\s*/, "") || f, build, kind, enclosure: ENCLOSURE.has(path) });
  }
  return out;
}

const BUILDS = ["with_uwb", "without_uwb"];
// Shared docs about the enclosure and printed parts only, which the bench
// rigs have none of.
const ENCLOSURE = new Set([
  "docs/design/03-mechanical-design.md",
  "docs/appendix/appendix-a-cad-parts.md",
  "docs/appendix/appendix-b-open-source-parts.md",
]);

// Docs are numbered in reading order; sort by number, then by build, so a
// build-specific doc appears at its place in the order.
const byNumber = (a, b) => a.path.split("/").pop().localeCompare(b.path.split("/").pop()) || a.path.localeCompare(b.path);

// Sidebar: the README, then Product, Design, Setup and the appendices —
// the order of the README's table of contents.
async function listDocs() {
  const entries = [{ path: "README.md", title: "README" }];
  for (const [folder, title] of [["product", "Product"], ["design", "Design"], ["setup", "Setup"]]) {
    const setup = folder === "setup";
    const kind = setup ? "setup" : null;
    entries.push({ section: title });
    if (setup)
      for (const b of BUILDS) {
        entries.push({ path: `docs/${b}/setup/README.md`, title: "Setup — start here", build: b, kind });
        entries.push({ path: `docs/${b}/bench/README.md`, title: "Bench test — start here", build: b, kind: "bench" });
      }
    const list = [...(await mdEntries(`docs/${folder}`, null, kind))];
    for (const b of BUILDS) {
      list.push(...(await mdEntries(`docs/${b}/${folder}`, b, kind)));
      if (setup) {
        list.push(...(await mdEntries(`docs/${b}/bench`, b, "bench")));
        list.push({ path: `docs/${b}/setup/13-assembly.html`, href: `docs/${b}/setup/assembly/index.html`, title: "13 — Assembly guide, interactive 3D", build: b, kind });
      }
    }
    list.sort(byNumber);
    entries.push(...list.map(({ href, ...e }) => (href ? { ...e, path: href } : e)));
    if (setup)
      for (const b of BUILDS) {
        entries.push({ path: `${b}/schematics/interactive/index.html`, title: "Wiring schematic, interactive", build: b, kind });
        entries.push({ path: `${b}/schematics/interactive/bench.html`, title: "Bench wiring schematic, interactive", build: b, kind: "bench" });
      }
  }
  entries.push({ section: "Appendices" });
  entries.push(...(await mdEntries("docs/appendix")).sort(byNumber));
  return entries;
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url ?? "/", "http://x");
    if (url.pathname === "/") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(PAGE);
      return;
    }
    if (url.pathname === "/api/docs") {
      res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify(await listDocs()));
      return;
    }
    const path = normalize(join(ROOT, decodeURIComponent(url.pathname)));
    if (!path.startsWith(ROOT) || path.includes("node_modules")) {
      res.writeHead(403).end("forbidden");
      return;
    }
    const body = await readFile(path);
    res.writeHead(200, {
      "Content-Type": MIME[extname(path)] ?? "application/octet-stream",
      "Cache-Control": "no-store",
    }).end(body);
  } catch {
    res.writeHead(404).end("not found");
  }
});

server.listen(PORT, () => {
  console.log(`SportCam docs → http://localhost:${PORT}`);
});
