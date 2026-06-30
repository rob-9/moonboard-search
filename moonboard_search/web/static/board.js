// MoonBoard 2024 hold-search front end.
// Renders an SVG board from /api/holds, lets the user mark holds, and queries
// /api/search. Board geometry is derived from the coord strings (column letter
// + row number) so it does not depend on stored x/y positions.

const CELL = 42;
const PAD = 26;
const RADIUS = 16;
const SVG_NS = "http://www.w3.org/2000/svg";

// state: coord -> "required" | "exclude" | "start" | "end"
const marks = new Map();
let mode = "required";

const boardEl = document.getElementById("board");
const resultsEl = document.getElementById("results");
const countEl = document.getElementById("count");

function parseCoord(coord) {
  const m = /^([A-Za-z]+)(\d+)$/.exec(coord);
  if (!m) return null;
  let col = 0;
  for (const ch of m[1].toUpperCase()) col = col * 26 + (ch.charCodeAt(0) - 64);
  return { col: col - 1, row: parseInt(m[2], 10) };
}

function buildBoard(holds) {
  const parsed = holds
    .map((h) => ({ coord: h.coord, ...parseCoord(h.coord) }))
    .filter((h) => h.col != null);
  if (!parsed.length) {
    boardEl.innerHTML = "<p class='hint'>No data yet. Run the scraper first.</p>";
    return;
  }
  const maxCol = Math.max(...parsed.map((h) => h.col));
  const maxRow = Math.max(...parsed.map((h) => h.row));
  const width = PAD * 2 + maxCol * CELL;
  const height = PAD * 2 + (maxRow - 1) * CELL;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  for (const h of parsed) {
    const cx = PAD + h.col * CELL;
    const cy = PAD + (maxRow - h.row) * CELL; // row 1 at bottom
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", cx);
    circle.setAttribute("cy", cy);
    circle.setAttribute("r", RADIUS);
    circle.setAttribute("class", "hold");
    circle.dataset.coord = h.coord;
    circle.addEventListener("click", () => onHoldClick(h.coord));
    svg.appendChild(circle);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", cx);
    label.setAttribute("y", cy + 3);
    label.setAttribute("class", "hold-label");
    label.textContent = h.coord;
    svg.appendChild(label);
  }
  boardEl.innerHTML = "";
  boardEl.appendChild(svg);
}

function onHoldClick(coord) {
  const current = marks.get(coord);
  if (mode === "required") {
    // cycle required -> exclude -> off
    if (current === "required") marks.set(coord, "exclude");
    else if (current === "exclude") marks.delete(coord);
    else marks.set(coord, "required");
  } else {
    // start / end: toggle
    if (current === mode) marks.delete(coord);
    else marks.set(coord, mode);
  }
  refreshHoldClasses();
  runSearch();
}

function refreshHoldClasses() {
  for (const c of boardEl.querySelectorAll(".hold")) {
    c.className.baseVal = "hold";
    const mark = marks.get(c.dataset.coord);
    if (mark) c.classList.add(mark);
  }
}

function collect(kind) {
  return [...marks.entries()]
    .filter(([, v]) => v === kind)
    .map(([k]) => k);
}

function buildQuery() {
  const p = new URLSearchParams();
  const required = collect("required");
  const exclude = collect("exclude");
  const start = collect("start");
  const end = collect("end");
  if (required.length) p.set("holds", required.join(","));
  if (exclude.length) p.set("exclude", exclude.join(","));
  if (start.length) p.set("start", start.join(","));
  if (end.length) p.set("end", end.join(","));

  const grade = document.getElementById("f-grade").value.trim();
  const angle = document.getElementById("f-angle").value;
  const repeats = document.getElementById("f-repeats").value;
  if (grade) p.set("grade", grade);
  if (angle) p.set("angle", angle);
  if (document.getElementById("f-benchmark").checked) p.set("benchmark", "1");
  if (repeats) p.set("min_repeats", repeats);
  return p;
}

async function runSearch() {
  const resp = await fetch("/api/search?" + buildQuery().toString());
  const data = await resp.json();
  renderResults(data);
}

function renderResults(problems) {
  countEl.textContent = `${problems.length} climb${problems.length === 1 ? "" : "s"}`;
  resultsEl.innerHTML = "";
  for (const p of problems) {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="r-name">${escapeHtml(p.name || "Untitled")}` +
      `${p.is_benchmark ? " <span class='badge'>★ benchmark</span>" : ""}</span>` +
      `<span class="r-meta">${escapeHtml(p.grade || "?")} · ${p.angle || "?"}° · ${p.repeats || 0} repeats</span>`;
    li.addEventListener("click", () => selectProblem(p.api_id, li));
    resultsEl.appendChild(li);
  }
}

async function selectProblem(id, li) {
  for (const el of resultsEl.querySelectorAll("li.selected")) {
    el.classList.remove("selected");
  }
  li.classList.add("selected");
  const resp = await fetch(`/api/problem/${id}`);
  if (!resp.ok) return;
  const problem = await resp.json();
  highlightMoves(problem.moves || []);
}

function highlightMoves(moves) {
  for (const c of boardEl.querySelectorAll(".hold")) {
    c.classList.remove("lit-start", "lit-mid", "lit-end");
  }
  for (const m of moves) {
    const el = boardEl.querySelector(`.hold[data-coord="${CSS.escape(m.coord)}"]`);
    if (!el) continue;
    if (m.is_start) el.classList.add("lit-start");
    else if (m.is_end) el.classList.add("lit-end");
    else el.classList.add("lit-mid");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Wire up controls.
for (const btn of document.querySelectorAll(".mode[data-mode]")) {
  btn.addEventListener("click", () => {
    mode = btn.dataset.mode;
    for (const b of document.querySelectorAll(".mode")) b.classList.remove("active");
    btn.classList.add("active");
  });
}
document.getElementById("clear").addEventListener("click", () => {
  marks.clear();
  refreshHoldClasses();
  runSearch();
});
for (const id of ["f-grade", "f-angle", "f-benchmark", "f-repeats"]) {
  document.getElementById(id).addEventListener("change", runSearch);
}

// Boot.
fetch("/api/holds")
  .then((r) => {
    if (!r.ok) throw new Error(`/api/holds returned ${r.status}`);
    return r.json();
  })
  .then((holds) => {
    buildBoard(holds);
    runSearch();
  })
  .catch((err) => {
    boardEl.innerHTML =
      "<p class='hint'>Could not load board data. Run the scraper, then reload.</p>";
    console.error(err);
  });
