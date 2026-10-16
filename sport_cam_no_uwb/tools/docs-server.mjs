#!/usr/bin/env node
/**
 * SportCam docs viewer — zero-dependency.
 *
 *   npm run docs        (or: node tools/docs-server.mjs)
 *   → http://localhost:8090
 *
 * Serves the repo statically and renders the markdown docs in a browser with
 * a sidebar, working images, and .md cross-links. Markdown is rendered
 * client-side with marked (CDN).
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
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
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
</style>
</head>
<body>
<nav><h1>📷 SportCam</h1><div id="toc">loading…</div></nav>
<main id="content"></main>
<script>
const toc = document.getElementById("toc");
const content = document.getElementById("content");
let pendingAnchor = null;

function currentDoc() {
  return decodeURIComponent(location.hash.slice(1)) || "README.md";
}

async function loadToc() {
  const docs = await (await fetch("/api/docs")).json();
  toc.innerHTML = docs.map(d => d.path.endsWith(".md")
    ? '<a href="#' + d.path + '" data-path="' + d.path + '">' + d.title + "</a>"
    : '<a href="/' + d.path + '" target="_blank">' + d.title + " ↗</a>").join("");
  markActive();
}

function markActive() {
  const cur = currentDoc();
  for (const a of toc.querySelectorAll("a"))
    a.classList.toggle("active", a.dataset.path === cur);
}

async function loadDoc() {
  const path = currentDoc();
  markActive();
  const res = await fetch("/" + path);
  if (!res.ok) { content.innerHTML = '<p class="err">not found: ' + path + "</p>"; return; }
  content.innerHTML = marked.parse(await res.text());
  const base = path.includes("/") ? path.slice(0, path.lastIndexOf("/") + 1) : "";
  // GitHub-style heading ids, so section anchors work
  const slug = (s) => s.toLowerCase().replace(/[^\\w\\s-]/g, "").trim().replace(/\\s+/g, "-");
  for (const h of content.querySelectorAll("h1,h2,h3,h4")) h.id = h.id || slug(h.textContent);
  // resolve relative images against the doc's directory
  for (const img of content.querySelectorAll("img")) {
    const src = img.getAttribute("src");
    if (src && !src.startsWith("http") && !src.startsWith("/"))
      img.src = "/" + base + src;
  }
  // .md cross-links stay inside the viewer; in-page anchors scroll;
  // everything else opens normally
  for (const a of content.querySelectorAll("a")) {
    const href = a.getAttribute("href");
    if (!href) continue;
    if (href.startsWith("http")) { a.target = "_blank"; continue; }
    if (href.startsWith("#")) {   // in-page anchor — don't fight the hash router
      const target = href.slice(1);
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        document.getElementById(target)?.scrollIntoView({ behavior: "smooth" });
      });
      continue;
    }
    const [clean, anchor] = href.split("#");
    if (clean.endsWith(".md")) {
      const resolved = new URL(clean, "http://x/" + base).pathname.slice(1);
      a.href = "#" + resolved;
      if (anchor) a.addEventListener("click", () => { pendingAnchor = anchor; });
    } else {
      a.href = "/" + new URL(clean, "http://x/" + base).pathname.slice(1);
      a.target = "_blank";
    }
  }
  if (pendingAnchor) {
    document.getElementById(pendingAnchor)?.scrollIntoView();
    pendingAnchor = null;
  } else {
    window.scrollTo(0, 0);
  }
  document.title = "SportCam docs — " + path;
}

window.addEventListener("hashchange", loadDoc);
loadToc().then(loadDoc);
</script>
</body>
</html>`;

async function listDocs() {
  const entries = [{ path: "README.md", title: "README" }];
  const files = (await readdir(join(ROOT, "docs"))).filter((f) => f.endsWith(".md")).sort();
  for (const f of files) {
    const first = (await readFile(join(ROOT, "docs", f), "utf8")).split("\n")[0];
    entries.push({ path: `docs/${f}`, title: first.replace(/^#\s*/, "") || f });
  }
  entries.push({ path: "docs/3d_printer/specifications.md", title: "3D printing specifications" });
  entries.push({ path: "docs/setup/README.md", title: "Setup — start here" });
  entries.push({ path: "docs/setup/assembly/index.html", title: "Setup 1: Assembly guide (interactive 3D)" });
  entries.push({ path: "docs/setup/wiring.md", title: "Setup 1a: Wiring guide" });
  entries.push({ path: "docs/setup/software_setup.md", title: "Setup 2: Software setup" });
  entries.push({ path: "schematics/interactive/index.html", title: "Wiring schematic (interactive)" });
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
