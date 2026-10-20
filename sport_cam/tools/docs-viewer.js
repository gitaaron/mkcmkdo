// SportCam docs viewer — the browser half of tools/docs-server.mjs.
//
// Renders the markdown docs with marked, keeps .md cross-links inside the
// viewer, and shows the docs for one build at a time. The build toggle
// (With UWB / Without UWB) is remembered in localStorage.
//
// What the toggle hides, in the build you are not viewing:
//   - sidebar entries for that build's own docs
//   - sections headed "With UWB" / "Without UWB", or "<heading>, with UWB"
//   - list items that start with the build's name in bold or as a link
//   - table columns whose header names only that build, and rows whose
//     first two cells name only that build — except in a table that follows
//     a <!--compare--> line, which compares the builds and keeps both
//   - the other half of a "[with UWB](…) · [without UWB](…)" link pair
//   - text marked in the markdown with HTML comments, which GitHub doesn't
//     show, so GitHub still reads as the combined doc for both builds:
//       <!--with_uwb-->…<!--/-->     on GitHub, and in the viewer with UWB
//       <!--without_uwb-->…<!--/-->  on GitHub, and in the viewer without UWB
//       <!--both-->…<!--/-->         on GitHub only (wording for both builds)
//       <!--with_uwb: …-->           in the viewer with UWB only
//       <!--without_uwb: …-->        in the viewer without UWB only
//     The last two hold markdown that replaces a <!--both--> passage; it
//     can't contain "--". On GitHub a line that starts with a comment is
//     raw HTML, so a marker never starts a line inside a paragraph: a
//     whole-paragraph passage puts each marker on a line of its own, with
//     blank lines around. Markers inside code are left alone.
//     tools/check-build-markers.py checks all of this.

const BUILDS = {
  with_uwb: "With UWB",
  without_uwb: "Without UWB",
};
const STORE_KEY = "sportcam-docs-build";

const toc = document.getElementById("toc");
const content = document.getElementById("content");
const toggle = document.getElementById("build-toggle");
let docs = [];
let source = null; // the current doc's markdown, for re-rendering on toggle
let pendingAnchor = null;

function loadBuild() {
  try {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved in BUILDS) return saved;
  } catch {}
  return "with_uwb";
}
let build = loadBuild();

function saveBuild() {
  try {
    localStorage.setItem(STORE_KEY, build);
  } catch {}
}

function currentDoc() {
  return decodeURIComponent(location.hash.slice(1)) || "README.md";
}

// The build a repo path belongs to, or null for a shared one.
function buildOfPath(path) {
  const m = /^(?:src\/)?(with_uwb|without_uwb)\//.exec(path);
  return m ? m[1] : null;
}

// The build a piece of text names, if it names exactly one.
function buildOfText(text) {
  const t = text.toLowerCase();
  const w = /\bwith[ _-]uwb\b|\buwb build\b/.test(t);
  const wo = /\bwithout[ _-]uwb\b|\bcamera-only\b/.test(t);
  return w === wo ? null : w ? "with_uwb" : "without_uwb";
}

// The build an in-page anchor belongs to: #with-uwb, #printed-parts-with-uwb…
function buildOfAnchor(anchor) {
  const m = /(?:^|-)(with|without)-uwb$/.exec(anchor);
  return m ? m[1] + "_uwb" : null;
}

const otherBuild = () => (build === "with_uwb" ? "without_uwb" : "with_uwb");

// --- toggle + sidebar ------------------------------------------------------

function renderToggle() {
  toggle.innerHTML = Object.entries(BUILDS)
    .map(([key, label]) => `<button type="button" data-build="${key}" aria-pressed="${key === build}">${label}</button>`)
    .join("");
}

toggle.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-build]");
  if (btn && btn.dataset.build !== build) setBuild(btn.dataset.build, { follow: true });
});

function renderToc() {
  toc.innerHTML = docs
    .filter((d) => !d.build || d.build === build)
    .map((d) =>
      d.section
        ? "<h2>" + d.section + "</h2>"
        : d.path.endsWith(".md")
        ? '<a href="#' + d.path + '" data-path="' + d.path + '">' + d.title + "</a>"
        : '<a href="/' + d.path + '" target="_blank">' + d.title + " ↗</a>",
    )
    .join("");
  markActive();
}

function markActive() {
  const cur = currentDoc();
  for (const a of toc.querySelectorAll("a")) a.classList.toggle("active", a.dataset.path === cur);
}

// Switch builds. With `follow`, a build-specific doc is swapped for the other
// build's copy of it (or that build's overview when there is none); a shared
// doc re-renders in place, staying at the same section where it still exists.
function setBuild(next, { follow = false, render: rerender = true } = {}) {
  if (next === build) return;
  build = next;
  saveBuild();
  renderToggle();
  renderToc();
  const path = currentDoc();
  const from = buildOfPath(path);
  if (follow && from && from !== build) {
    const twin = path.replace(from, build);
    const known = docs.some((d) => d.path === twin);
    location.hash = known ? twin : `${build}/README.md`;
    return;
  }
  if (rerender && source !== null && !from) {
    const keep = firstVisibleHeading();
    render(path, source);
    if (keep && document.getElementById(keep)) document.getElementById(keep).scrollIntoView();
  }
}

function firstVisibleHeading() {
  let last = null;
  for (const h of content.querySelectorAll("h1,h2,h3,h4")) {
    if (h.getBoundingClientRect().top > 80) break;
    last = h.id;
  }
  return last;
}

// --- rendering -------------------------------------------------------------

// Markers inside code (fenced blocks, `spans`) are literal text, as on GitHub.
function applyMarkers(md) {
  const code = [];
  const hide = (m) => `\u0000${code.push(m) - 1}\u0000`;
  return md
    .replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, hide)
    .replace(/`[^`\n]+`/g, hide)
    .replace(/<!--(with_uwb|without_uwb):([\s\S]*?)-->/g, (_, tag, body) => (tag === build ? body.replace(/^ /, "") : ""))
    .replace(/<!--\s*(with_uwb|without_uwb|both)\s*-->([\s\S]*?)<!--\s*\/\s*-->/g, (_, tag, body) =>
    tag === build ? body : "",
    )
    .replace(/\u0000(\d+)\u0000/g, (_, i) => code[i]);
}

// GitHub-style heading ids, so section anchors work
const slug = (s) =>
  s
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");

function render(path, md) {
  content.innerHTML = marked.parse(applyMarkers(md));
  const base = path.includes("/") ? path.slice(0, path.lastIndexOf("/") + 1) : "";
  for (const h of content.querySelectorAll("h1,h2,h3,h4")) h.id = h.id || slug(h.textContent);
  hideOtherBuild();
  // resolve relative images against the doc's directory
  for (const img of content.querySelectorAll("img")) {
    const src = img.getAttribute("src");
    if (src && !src.startsWith("http") && !src.startsWith("/")) img.src = "/" + base + src;
  }
  // .md cross-links stay inside the viewer; in-page anchors scroll;
  // everything else opens normally. From a shared doc, a link into the other
  // build's files goes to this build's copy when there is one (unless its
  // text names the other build); a link still into the other build's docs
  // or sections switches the toggle on the way.
  for (const a of content.querySelectorAll("a")) {
    const href = a.getAttribute("href");
    if (!href) continue;
    if (href.startsWith("http")) {
      a.target = "_blank";
      continue;
    }
    if (href.startsWith("#")) {
      // in-page anchor — don't fight the hash router
      const target = href.slice(1);
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        const to = buildOfAnchor(target);
        if (to) setBuild(to);
        document.getElementById(target)?.scrollIntoView({ behavior: "smooth" });
      });
      continue;
    }
    const [clean, anchor] = href.split("#");
    let resolved = new URL(clean, "http://x/" + base).pathname.slice(1);
    const into = buildOfPath(resolved);
    if (into && into !== build && !buildOfPath(path) && !buildOfText(a.textContent)) {
      const twin = resolved.replace(into + "/", build + "/");
      if (clean.endsWith(".md")) {
        if (docs.some((d) => d.path === twin)) resolved = twin;
      } else {
        fetch("/" + twin, { method: "HEAD" })
          .then((r) => r.ok && (a.href = "/" + twin))
          .catch(() => {});
      }
    }
    if (clean.endsWith(".md")) {
      a.href = "#" + resolved;
      a.addEventListener("click", (ev) => {
        if (ev.button || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return; // new tab etc.
        ev.preventDefault();
        const to = buildOfPath(resolved) ?? (anchor ? buildOfAnchor(anchor) : null);
        if (resolved === path) {
          // same doc: hashchange won't fire, so switch and scroll here
          if (to) setBuild(to);
          if (anchor) document.getElementById(anchor)?.scrollIntoView();
          return;
        }
        if (to) setBuild(to, { render: false });
        pendingAnchor = anchor || null;
        location.hash = resolved;
      });
    } else {
      a.href = "/" + resolved;
      a.target = "_blank";
    }
  }
}

// A table right after a <!--compare--> comment.
function comparesBuilds(table) {
  let n = table.previousSibling;
  while (n && n.nodeType === Node.TEXT_NODE && !n.textContent.trim()) n = n.previousSibling;
  return n?.nodeType === Node.COMMENT_NODE && n.textContent.trim() === "compare";
}

function hideOtherBuild() {
  const other = otherBuild();

  // Sections: "With UWB", "Without UWB", "Something, with UWB". A section
  // runs to the next heading of the same or a higher level; the rule (---)
  // that introduces it goes with it.
  const headingBuild = (h) => {
    const m = /^(?:(with|without) uwb|.*, (with|without) uwb)$/i.exec(h.textContent.trim());
    return m ? (m[1] || m[2]).toLowerCase() + "_uwb" : null;
  };
  const kids = [...content.children];
  for (let i = 0; i < kids.length; i++) {
    const h = kids[i];
    if (!/^H[1-6]$/.test(h.tagName) || headingBuild(h) !== other) continue;
    const level = Number(h.tagName[1]);
    if (kids[i - 1]?.tagName === "HR") kids[i - 1].remove();
    let j = i;
    for (; j < kids.length; j++) {
      const el = kids[j];
      if (j > i && /^H[1-6]$/.test(el.tagName) && Number(el.tagName[1]) <= level) break;
      el.remove();
    }
    i = j - 1;
  }
  while (content.lastElementChild?.tagName === "HR") content.lastElementChild.remove();

  // List items that open with the build's name: "- **[With UWB](…)**: …"
  for (const li of content.querySelectorAll("li")) {
    const first = li.firstElementChild;
    if (!first || !/^(STRONG|A|EM)$/.test(first.tagName)) continue;
    if (!li.textContent.trim().startsWith(first.textContent.trim())) continue;
    const name = first.textContent.trim().toLowerCase();
    if (name === BUILDS[other].toLowerCase()) li.remove();
  }

  // Tables: columns headed by only the other build, rows labelled by it.
  for (const table of content.querySelectorAll("table")) {
    if (comparesBuilds(table)) continue;
    const heads = [...table.querySelectorAll("thead th")];
    const drop = heads.map((th, i) => (buildOfText(th.textContent) === other ? i : -1)).filter((i) => i >= 0);
    if (drop.length && drop.length < heads.length - 1)
      for (const tr of table.querySelectorAll("tr"))
        for (const i of [...drop].reverse()) tr.children[i]?.remove();
    for (const tr of table.querySelectorAll("tbody tr")) {
      const label = [...tr.children].slice(0, 2).map((td) => td.textContent).join(" ");
      if (buildOfText(label) === other) tr.remove();
    }
  }

  // Link pairs: "[with UWB](a) · [without UWB](b)" keeps only this build's.
  const isSep = (n) => n?.nodeType === Node.TEXT_NODE && /^[\s·,/]*(?:or|and)?[\s·,/]*$/.test(n.textContent);
  const linkName = (n) => (n?.nodeType === Node.ELEMENT_NODE && n.tagName === "A" ? n.textContent.trim().toLowerCase() : null);
  for (const a of [...content.querySelectorAll("a")]) {
    if (linkName(a) !== BUILDS[other].toLowerCase()) continue;
    const mine = BUILDS[build].toLowerCase();
    if (isSep(a.nextSibling) && linkName(a.nextSibling.nextSibling) === mine) {
      a.nextSibling.remove();
      a.remove();
    } else if (isSep(a.previousSibling) && linkName(a.previousSibling.previousSibling) === mine) {
      a.previousSibling.remove();
      a.remove();
    }
  }
}

async function loadDoc() {
  const path = currentDoc();
  const owner = buildOfPath(path);
  if (owner) setBuild(owner); // a deep link to one build's doc picks that build
  markActive();
  const res = await fetch("/" + path);
  if (!res.ok) {
    source = null;
    content.innerHTML = '<p class="err">not found: ' + path + "</p>";
    return;
  }
  source = await res.text();
  render(path, source);
  if (pendingAnchor) {
    document.getElementById(pendingAnchor)?.scrollIntoView();
    pendingAnchor = null;
  } else {
    window.scrollTo(0, 0);
  }
  document.title = "SportCam docs — " + path;
}

window.addEventListener("hashchange", loadDoc);
renderToggle();
fetch("/api/docs")
  .then((r) => r.json())
  .then((list) => {
    docs = list;
    renderToc();
  })
  .then(loadDoc);
