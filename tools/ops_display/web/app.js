// SPDX-License-Identifier: GPL-3.0-or-later
// Fork Operations Display: renders the server's snapshot. Display only: this page sends nothing but GET
// requests for /snapshot, and keeps nothing (the "seen" marks and the theme live in this window's memory).
// A panel is rebuilt only when its own data changed; clocks and countdowns tick in place.
"use strict";

let S = null, skew = 0, lastOk = 0, webVersion = null, selLane = null;
const seen = new Set(), sigs = {};
const $ = (s, r = document) => r.querySelector(s);
const NS = "http://www.w3.org/2000/svg";

function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v; else e.setAttribute(k, v);
  }
  for (const k of kids.flat(3)) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}
function svg(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
const light = (st) => h("span", { class: "light " + st, role: "img", "aria-label": st });
const sect = (label, right) => h("div", { class: "sect" }, h("span", { class: "lbl" }, label), h("span", { class: "fill" }), right ? h("span", { class: "lbl num" }, right) : null);
function changed(key, data) { const s = JSON.stringify(data); if (sigs[key] === s) return false; sigs[key] = s; return true; }

// ---------- formatting (all times EST, 12-hour) ----------
const now = () => (Date.now() + skew) / 1000;
const est = (t) => new Date((t - 18000) * 1000);
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function hm(t, secs) {
  const d = est(t), H = d.getUTCHours(), p = (n) => String(n).padStart(2, "0");
  return `${H % 12 || 12}:${p(d.getUTCMinutes())}${secs ? ":" + p(d.getUTCSeconds()) : ""} ${H < 12 ? "AM" : "PM"}`;
}
function when(t) {
  if (!t) return "";
  const d = est(t), n = est(now());
  if (d.getUTCFullYear() === n.getUTCFullYear() && d.getUTCMonth() === n.getUTCMonth() && d.getUTCDate() === n.getUTCDate()) return hm(t);
  if (Math.abs(now() - t) < 6 * 86400) return DAYS[d.getUTCDay()] + " " + hm(t);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${hm(t)}`;
}
const day = (t) => { const d = est(t); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`; };
function span(s) {
  s = Math.max(0, Math.round(s));
  if (s < 90) return s + " s";
  if (s < 5400) return Math.round(s / 60) + " min";
  if (s < 2 * 86400) { const m = Math.round(s / 60); return Math.floor(m / 60) + " h" + (m % 60 ? " " + (m % 60) + " min" : ""); }
  const hrs = Math.round(s / 3600); return Math.floor(hrs / 24) + " d" + (hrs % 24 ? " " + (hrs % 24) + " h" : "");
}
function countdown(until) {
  const s = Math.round(until - now());
  if (s <= 0) return "due";
  const m = Math.floor(s / 60), r = String(s % 60).padStart(2, "0");
  return (m >= 60 ? Math.floor(m / 60) + ":" + String(m % 60).padStart(2, "0") : m) + ":" + r;
}
function pos(n) {
  if (n == null) return "unknown";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + " B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + " M";
  if (n >= 1e3) return Math.round(n / 1e3) + " K";
  return String(n);
}
const sg = (v, d = 1) => (v == null ? "n/a" : +Math.abs(v).toFixed(d) === 0 ? (0).toFixed(d) : (v < 0 ? "−" : "+") + Math.abs(v).toFixed(d));
const int = (n) => (n == null ? "n/a" : n.toLocaleString("en-US"));
const elo = (e, err, d = 1) => [sg(e, d), h("span", { class: "dim" }, " ± " + (err == null ? "?" : err.toFixed(d)))];
function spark(vals) {
  if (!vals || vals.length < 2) return null;
  const w = 72, ht = 20, lo = Math.min(...vals), hi = Math.max(...vals), sp = hi - lo || 1;
  const pts = vals.map((v, i) => [2 + i * (w - 6) / (vals.length - 1), 3 + (ht - 6) * (1 - (v - lo) / sp)]);
  const line = "M" + pts.map((p) => p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" L");
  const s = svg("svg", { class: "spark", viewBox: `0 0 ${w} ${ht}`, role: "img", "aria-label": "trend" });
  s.append(svg("path", { class: "a", d: line + ` L${pts.at(-1)[0]} ${ht} L${pts[0][0]} ${ht} Z` }), svg("path", { class: "l", d: line }), svg("circle", { cx: pts.at(-1)[0], cy: pts.at(-1)[1], r: 2.4 }));
  return s;
}
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---------- strip ----------
function renderStrip() {
  const o = S.overview || {}, g = o.latest, ref = g && g.reference;
  if (changed("strip", [o.net, o.net_since, g, o.commit, o.branch, o.adoptions && o.adoptions.week])) {
    $("#s-net").textContent = o.net || "unknown";
    const since = o.net_since && /^\d{4}-\d\d-\d\d$/.test(o.net_since) ? `${MONTHS[+o.net_since.slice(5, 7) - 1]} ${+o.net_since.slice(8)}` : o.net_since;
    $("#s-net-sub").textContent = since ? "default since " + since : "";
    const bal = (o.series || []).filter((x) => x.book === "balanced");
    $("#s-rating").replaceChildren(g ? g.rating.toFixed(1) : "none", g ? h("small", {}, " ± " + (g.err || 0).toFixed(1)) : null);
    $("#s-rating-spark").replaceChildren(spark(bal.slice(-5).map((x) => x.rating)) || "");
    $("#s-rating-sub").textContent = g ? `gauntlet of ${day(g.at)}, ${int(g.played)} games, ${g.anchor_count} anchors, engine ${g.commit}` : "no gauntlet found";
    $("#s-gap-lbl").textContent = ref ? "Gap to " + ref.name : "Gap to the reference engine";
    $("#s-gap").textContent = ref ? sg(ref.elo) + " Elo" : "n/a";
    const gaps = bal.filter((x) => x.reference).map((x) => x.reference.elo);
    $("#s-gap-spark").replaceChildren(spark(gaps) || "");
    $("#s-gap-sub").textContent = ref ? `95% interval ${sg(ref.lo)} to ${sg(ref.hi)}` + (gaps.length > 1 ? `; was ${sg(gaps[0])} on ${day(bal.find((x) => x.reference).at)}` : "") : "";
    const list = (o.adoptions && o.adoptions.list) || [], days = [];
    for (let i = 6; i >= 0; i--) { const d = est(now() - i * 86400), key = d.toISOString().slice(0, 10); days.push([`${DAYS[d.getUTCDay()]} ${d.getUTCDate()}`, list.filter((a) => a.date === key).length]); }
    const mx = Math.max(1, ...days.map((d) => d[1]));
    $("#s-adopt").textContent = o.adoptions ? o.adoptions.week : "n/a";
    $("#s-adopt-days").replaceChildren(...days.map(([d, n]) => h("i", { class: n ? "" : "zero", style: `height:${(n / mx) * 100}%`, title: `${d}: ${n} adopted` })));
    $("#s-adopt-sub").textContent = "search and engine changes, by day";
    $("#s-commit").textContent = o.commit || "unknown";
    $("#s-commit-sub").textContent = o.branch ? "branch " + o.branch : "";
  }
}
function renderHealth() {
  const list = S.alerts || [], crit = list.filter((a) => a.tier === "critical").length, att = list.filter((a) => a.tier === "attention" && !seen.has(a.id)).length;
  if (!changed("health", [crit, att])) return;
  const st = crit ? "failure" : att ? "attention" : "nominal", el = $("#health");
  el.className = st === "failure" ? "failure" : "";
  el.replaceChildren(h("span", { style: "font-size:1.6rem; display:flex" }, light(st)),
    h("div", {}, h("div", { class: "word" + (st === "failure" ? "" : " st-" + st) }, crit ? "CRITICAL" : att ? "ATTENTION" : "NOMINAL"),
      h("div", { class: "sub" }, crit ? `${crit} critical, ${att} to review` : att ? `${att} to review, none critical` : "nothing needs attention")));
}

// ---------- testing ----------
function llrBar(v) {
  const lo = v.lo, hi = v.hi, val = v.last ? v.last.llr : 0, spn = hi - lo, p = (x) => ((Math.max(lo, Math.min(hi, x)) - lo) / spn) * 100, z = p(0), m = p(val);
  return h("div", { class: "llr", title: "Log-likelihood ratio: the test ends when it reaches either end" },
    h("span", { class: "cap", style: "left:0" }, "reject at " + sg(lo, 2)), h("span", { class: "cap", style: "right:0" }, "accept at " + sg(hi, 2)),
    h("div", { class: "track" }), h("div", { class: "fill", style: `left:${Math.min(z, m)}%; width:${Math.abs(m - z)}%` }),
    h("div", { class: "zero", style: `left:${z}%` }), h("div", { class: "mark", style: `left:${m}%` }),
    h("span", { class: "val num", style: `left:${Math.max(8, Math.min(92, m))}%` }, "LLR " + sg(val, 2)));
}
const KIND = { screen: "Fixed-node screen", stc: "Short time control", ltc: "Long time control" };
function laneCard(L) {
  const v = L.sprt || {}, it = L.item, bad = L.state === "down" || L.state === "stopped";
  const st = bad ? "failure" : L.state === "idle" ? "idle" : "active";
  const tip = it ? [`queue item ${it.key}`, v.name ? `test ${v.name}` : "", v.flight ? `GitHub run ${v.flight.run}` : "", L.marker ? `current item from the lane's own marker (${L.marker})` : "current item inferred from the queue (no fresh marker)", it.comment || ""].filter(Boolean).join("\n") : `job ${L.job}`;
  const c = h("div", { class: "lane" + (bad ? " failure" : "") + (selLane === L.id ? " selected" : ""), title: tip, "data-lane": L.id });
  const kind = v.klass ? KIND[v.klass] + (v.design && v.design.kind === "network" ? ", net promotion test" : v.is_sprt ? " SPRT" : "") : it ? it.kind : "";
  const stage = v.stage_no && v.stage_count ? `Stage ${v.stage_no} of ${v.stage_count}` : "";
  c.append(h("div", { class: "top" }, light(st), h("span", { class: "tag" }, `Lane ${L.id}` + (kind ? " · " + kind : "")),
    h("span", { class: "tag", style: "margin-left:auto" }, { down: "down", stopped: "stopped", idle: "idle", starting: stage || "starting", testing: stage }[L.state])));
  if (!it) {
    c.append(h("div", { class: "name" }, L.state === "down" ? "The queue runner is not running" : "Nothing to run"),
      h("div", { class: "meta" }, L.state === "down" ? `Job ${L.job} has no live process.` : L.pending ? `${L.pending} items are waiting on a gate or a retry timer.` : "The queue is empty."));
    return c;
  }
  c.append(h("div", { class: "name" }, it.title), it.about ? h("div", { class: "meta" }, it.about) : null);
  const last = v.last, fl = v.flight, kv = h("div", { class: "kv" });
  kv.append(h("div", {}, h("div", { class: "lbl" }, last ? "Elo, 95% interval" : "Elo"), h("div", { class: "v num" }, last ? [sg(last.elo, 2), h("small", {}, " ± " + (last.elo_err == null ? "?" : last.elo_err.toFixed(2)))] : h("span", { class: "dim" }, "pending"))),
    h("div", {}, h("div", { class: "lbl" }, "Games"), h("div", { class: "v num" }, last ? int(last.games) : "0", v.cap_games ? h("small", {}, " of " + int(v.cap_games)) : null)),
    h("div", {}, h("div", { class: "lbl" }, bad ? "Stopped" : "Next result in"), h("div", { class: "v num" }, bad ? "" : fl && fl.eta ? h("span", { "data-until": fl.eta }, countdown(fl.eta)) : h("span", { class: "dim", style: "font-size:0.9rem" }, fl ? "no timing yet" : "between stages"))));
  c.append(kv);
  if (v.prelim) {
    c.append(h("div", { class: "prelim", title: "Combined from the shards' progress records of the stage now running, added to the finished stages. It moves until the stage ends." },
      h("span", { class: "chip" }, "preliminary"), h("span", { class: "num" }, elo(v.prelim.elo, v.prelim.elo_err, 2)), h("span", { class: "dim" }, `Elo over ${int(v.prelim.games)} games; ${int(v.prelim.stage_games)} of this stage's from ${v.prelim.shards} shards, as of ${when(v.prelim.at)}`)));
  }
  if (v.is_sprt && v.lo != null && v.hi != null) c.append(llrBar(v));
  if (L.state === "stopped") c.append(h("div", { class: "meta st-failure" }, v.stopped || "its run failed"));
  else if (fl) {
    const sh = v.shards;
    c.append(h("div", { class: "rowline" }, h("span", { class: "dim" }, `Running since ${when(fl.dispatched)}` + (v.typical_min ? `; usually ${Math.round(v.typical_min)} min a stage` : "")),
      sh ? h("span", { class: "num", title: "shard jobs finished in the GitHub run" }, `${sh.done} of ${sh.total} shards` + (sh.failed ? `, ${sh.failed} failed` : "")) : null));
    if (sh) c.append(h("div", { class: "bar act" }, h("i", { style: `width:${(sh.done / Math.max(1, sh.total)) * 100}%` })));
    if (fl.latest && v.is_sprt) c.append(h("div", { class: "meta faint" }, `At the latest ${when(fl.latest)}, if it runs to its game limit`));
  }
  return c;
}
function renderTesting() {
  const lanes = S.lanes || [], queue = S.queue || [], verdicts = S.verdicts || [];
  if (selLane == null || !lanes.find((l) => l.id === selLane)) selLane = (lanes.find((l) => l.sprt && l.sprt.stages && l.sprt.stages.length) || lanes[0] || {}).id || null;
  if (changed("lanes", [lanes, selLane])) {
    const sel = lanes.find((l) => l.id === selLane), v = sel && sel.sprt, d = v && v.design;
    const facts = !v || !d ? [] : [["Test", v.name], ["Decision rule", v.is_sprt ? `accept at ${sg(d.elo1, 0)} nElo, reject at ${sg(d.elo0, 0)}` + (d.alpha ? `; ${d.alpha * 100}% false accepts, ${d.beta * 100}% false rejects` : "") : "none: a fixed-length measurement"],
      d.futility_after ? ["Early stop", `after stage ${d.futility_after} if nElo is below 0`] : null, d.tc ? ["Time control", d.tc + " s"] : null,
      ["Stage", (d.games_per_stage ? int(d.games_per_stage) + " games; " : "") + (d.cap ? `at most ${d.cap} stage${d.cap > 1 ? "s" : ""}` + (v.cap_games ? ` (${int(v.cap_games)} games)` : "") : "")],
      ["Engines", `base ${d.base || "?"}, test ${d.test || "?"}`], d.idea ? ["Idea", d.idea + (d.try ? `, try ${d.try}` : "")] : null,
      v.flight && v.flight.latest ? ["Latest end", when(v.flight.latest) + " if it runs to its game limit"] : null, sel.item && sel.item.comment ? ["Queue note", sel.item.comment] : null].filter(Boolean);
    $("#t-col1").replaceChildren(...(lanes.length ? lanes.map(laneCard) : [h("div", { class: "empty" }, "No lane was found (no github lock file).")]),
      h("div", { class: "detail" }, facts.length ? [h("div", { style: "margin:0.4rem 0" }, sect(`Lane ${selLane}: how this test is run`)), h("div", { class: "list" }, facts.flatMap(([k, t]) => [h("span", { class: "lbl" }, k), h("span", {}, t)]))] : null));
    document.querySelectorAll("#t-col1 .lane").forEach((el) => el.addEventListener("click", () => { if ($("#main").dataset.focus === "2") { selLane = el.dataset.lane; delete sigs.lanes; delete sigs.lanecharts; renderTesting(); } }));
    $("#age-test").textContent = lanes.map((l) => `${l.id}: ${l.state}`).join(" · ");
  }
  if (changed("queue", [queue, verdicts])) {
    const q = h("div", { class: "q" });
    for (const it of queue) q.append(h("span", { class: "n" }, it.lane), h("span", { class: "t", title: [it.key, it.comment || ""].join("\n") }, it.title, it.about ? h("span", {}, " · " + it.about) : null),
      h("span", { class: "k" }, it.state === "pending" ? it.kind : it.state === "retry" ? `retry ${when(it.retry_at)}` : `${it.kind}, gated`));
    const per = {}; for (const it of queue) per[it.lane] = (per[it.lane] || 0) + 1;
    const tb = h("table", { id: "t-verdicts" }, h("tr", {}, h("th", {}, "Ended"), h("th", {}, "Test"), h("th", { class: "r" }, "Elo ± 95%")));
    for (const v of verdicts) {
      const k = v.outcome.kind, st = k === "passed" ? "nominal" : k === "stopped" || k === "interrupted" || k === "other" ? "attention" : "idle";
      tb.append(h("tr", { title: `test ${v.name}\n${v.outcome.meaning}` }, h("td", { class: "nw faint num" }, when(v.at)),
        h("td", {}, h("div", {}, v.title), h("div", { class: "sub2" }, light(st), `${v.outcome.label}${v.adopted ? " and adopted" : ""} · ${v.klass} · ${int(v.games)} games`)),
        h("td", { class: "r nw num" }, v.elo == null ? "n/a" : elo(v.elo, v.err))));
    }
    $("#t-col3").replaceChildren(sect("Queue ahead", Object.entries(per).map(([k, n]) => `${n} on ${k}`).join(", ") || "empty"), queue.length ? q : h("div", { class: "empty" }, "Nothing is waiting."),
      queue.length > 6 ? h("div", { class: "faint compact-only", style: "font-size:0.8rem" }, `and ${queue.length - 6} more; press 2 for the whole queue`) : null,
      sect("Recent verdicts", "last 3 days"), verdicts.length ? tb : h("div", { class: "empty" }, "No test ended in the last 3 days."));
  }
  const sel = lanes.find((l) => l.id === selLane), v = sel && sel.sprt;
  if (changed("lanecharts", [v && v.stages, v && v.lo, v && v.hi, selLane])) {
    const c2 = $("#t-col2");
    if (!v || !v.stages || !v.stages.length) c2.replaceChildren(h("div", { class: "empty" }, v ? "This test has no finished stage yet; its first result arrives when the stage ends." : "No test is running on this lane."));
    else {
      const t = h("table", {}, h("tr", {}, ...["Stage", "Merged", "Minutes", "Games", "Elo ± 95%", "LLR"].map((x, i) => h("th", { class: i > 1 ? "r" : "" }, x))));
      v.stages.forEach((s, i) => t.append(h("tr", { title: `GitHub run ${s.run}` }, h("td", { class: "num" }, i + 1), h("td", { class: "num faint" }, when(s.merged)), h("td", { class: "r num" }, s.dispatched ? Math.round((s.merged - s.dispatched) / 60) : ""),
        h("td", { class: "r num" }, int(s.games)), h("td", { class: "r num" }, elo(s.elo, s.elo_err, 2)), h("td", { class: "r num" }, sg(s.llr, 2)))));
      c2.replaceChildren(...(v.is_sprt ? [sect(`Lane ${selLane}: likelihood ratio by stage`), h("div", { class: "chart", id: "ch-llr", style: "min-height:10rem" }, svg("svg"), h("div", { class: "tip" }))] : []),
        sect("Elo with its 95% interval by stage"), h("div", { class: "chart", id: "ch-elo", style: "min-height:10rem" }, svg("svg"), h("div", { class: "tip" })),
        sect("Game pairs by score for the test engine (0, ½, 1, 1½, 2 points)"), h("div", { class: "chart", id: "ch-pt", style: "min-height:6rem; flex:0.6" }, svg("svg"), h("div", { class: "tip" })), t);
      requestAnimationFrame(drawLaneCharts);
    }
  }
}

// ---------- charts ----------
function frame(el, pad) {
  const s = $("svg", el), w = el.clientWidth, ht = el.clientHeight; s.replaceChildren(); s.setAttribute("viewBox", `0 0 ${w} ${ht}`);
  return { s, w, ht, x0: pad.l, x1: w - pad.r, y0: pad.t, y1: ht - pad.b };
}
function tipFor(el, pts, html) {
  const tip = $(".tip", el);
  el.onpointermove = (ev) => {
    if (!pts.length) return;
    const r = el.getBoundingClientRect(), x = ev.clientX - r.left; let best = pts[0];
    for (const p of pts) if (Math.abs(p.px - x) < Math.abs(best.px - x)) best = p;
    tip.replaceChildren(...html(best).filter(Boolean)); tip.style.display = "block";
    tip.style.left = Math.max(0, Math.min(best.px + 10, r.width - tip.offsetWidth - 4)) + "px"; tip.style.top = Math.max(0, best.py - tip.offsetHeight - 8) + "px";
  };
  el.onpointerleave = () => { tip.style.display = "none"; };
}
function nice(lo, hi, n) { const stepRaw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(stepRaw))), step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= stepRaw); const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6)); return out; }
function drawRating() {
  const el = $("#ch-rating"), o = (S && S.overview) || {}; if (!el.clientWidth || !el.clientHeight) return;
  const pts0 = (o.series || []).filter((x) => x.book === "balanced");
  const f = frame(el, { l: 40, r: 78, t: 12, b: 20 }), ink = cssv("--ink"), ink2 = cssv("--ink-2"), ink3 = cssv("--ink-3"), rule = cssv("--rule"), panel = cssv("--panel");
  if (!pts0.length) { f.s.append(svg("text", { class: "lab", x: f.x0, y: f.y0 + 14 }, "No gauntlet result was found.")); return; }
  const ref = pts0.at(-1).reference, t0 = pts0[0].at, t1 = Math.max(pts0.at(-1).at, t0 + 86400);
  const vals = pts0.flatMap((p) => [p.rating - (p.err || 0), p.rating + (p.err || 0)]).concat(ref ? [ref.rating] : []);
  const lo = Math.min(...vals) - 20, hi = Math.max(...vals) + 25;
  const X = (t) => f.x0 + 8 + ((t - t0) / (t1 - t0)) * (f.x1 - f.x0 - 16), Y = (v) => f.y1 - ((v - lo) / (hi - lo)) * (f.y1 - f.y0);
  for (const g of nice(lo, hi, 5)) f.s.append(svg("line", { x1: f.x0, x2: f.x1, y1: Y(g), y2: Y(g), stroke: rule, "stroke-width": 1 }), svg("text", { x: f.x0 - 6, y: Y(g) + 3, "text-anchor": "end" }, g));
  let lastLabel = -1e9;
  for (const p of pts0) if (X(p.at) - lastLabel > 46) { f.s.append(svg("text", { x: X(p.at), y: f.ht - 5, "text-anchor": "middle" }, day(p.at))); lastLabel = X(p.at); }
  if (ref) f.s.append(svg("line", { x1: f.x0, x2: f.x1, y1: Y(ref.rating), y2: Y(ref.rating), stroke: ink3, "stroke-width": 1.5 }), svg("text", { class: "lab", x: f.x1 + 6, y: Y(ref.rating) + 3 }, ref.name));
  const segs = [[]];
  for (const p of pts0) { if (p.anchors_changed) { f.s.append(svg("line", { x1: X(p.at) - 7, x2: X(p.at) - 7, y1: f.y0, y2: f.y1, stroke: rule, "stroke-width": 1 }), svg("text", { x: X(p.at) - 3, y: f.y0 + 9 }, "anchors changed")); segs.push([]); } segs.at(-1).push(p); }
  for (const sg2 of segs) if (sg2.length > 1) f.s.append(svg("path", { d: "M" + sg2.map((p) => X(p.at) + " " + Y(p.rating)).join(" L"), fill: "none", stroke: ink2, "stroke-width": 2, "stroke-linejoin": "round" }));
  const pts = [];
  for (const p of pts0) {
    if (p.err) f.s.append(svg("line", { x1: X(p.at), x2: X(p.at), y1: Y(p.rating - p.err), y2: Y(p.rating + p.err), stroke: ink2, "stroke-width": 1 }));
    f.s.append(svg("circle", { cx: X(p.at), cy: Y(p.rating), r: 4, fill: ink, stroke: panel, "stroke-width": 2 }));
    pts.push({ px: X(p.at), py: Y(p.rating), p });
  }
  const last = pts0.at(-1);
  f.s.append(svg("text", { class: "lab", x: X(last.at) + 8, y: Y(last.rating) + 3, style: `fill:${ink}` }, "Fork " + last.rating.toFixed(1)));
  if (ref) f.s.append(svg("line", { x1: X(last.at), x2: X(last.at), y1: Y(last.rating + (last.err || 0)) - 4, y2: Y(ref.rating) + 3, stroke: ink3, "stroke-width": 1 }),
    svg("text", { class: "lab", x: X(last.at) + 8, y: (Y(last.rating) + Y(ref.rating)) / 2 + 3 }, "gap " + sg(ref.elo)));
  tipFor(el, pts, ({ p }) => [h("div", {}, h("b", {}, p.rating.toFixed(1) + " ± " + (p.err || 0).toFixed(1)), " Elo"), h("div", { class: "dim" }, `${when(p.at)}, engine ${p.commit}, ${p.anchor_count} anchors, ${int(p.played)} games`),
    p.reference ? h("div", { class: "dim" }, `gap to ${p.reference.name}: ${sg(p.reference.elo)}`) : null, p.transfer ? h("div", { class: "dim" }, `share of self-play gains kept: ${p.transfer.ratio.toFixed(2)}`) : null]);
}
function drawLaneCharts() {
  const L = ((S && S.lanes) || []).find((l) => l.id === selLane), v = L && L.sprt; if (!v || !v.stages || !v.stages.length) return;
  const ink = cssv("--ink"), ink2 = cssv("--ink-2"), ink3 = cssv("--ink-3"), rule = cssv("--rule"), panel = cssv("--panel");
  const n = Math.max(v.stage_count || 0, v.stages.length), st = v.stages.map((s, i) => ({ ...s, n: i + 1 }));
  let el = $("#ch-llr");
  if (el && el.clientWidth && v.lo != null) {
    const f = frame(el, { l: 44, r: 84, t: 10, b: 20 }), lo = v.lo - 0.35, hi = v.hi + 0.35, X = (k) => f.x0 + (k / n) * (f.x1 - f.x0), Y = (x) => f.y1 - ((Math.max(lo, Math.min(hi, x)) - lo) / (hi - lo)) * (f.y1 - f.y0);
    for (let k = 0; k <= n; k++) if (n <= 9 || k % 2 === 0) f.s.append(svg("text", { x: X(k), y: f.ht - 5, "text-anchor": "middle" }, k ? "stage " + k : "start"));
    for (const [val, t, w] of [[v.hi, "accept " + sg(v.hi, 2), 1.5], [0, "0", 1], [v.lo, "reject " + sg(v.lo, 2), 1.5]]) f.s.append(svg("line", { x1: f.x0, x2: f.x1, y1: Y(val), y2: Y(val), stroke: val ? ink3 : rule, "stroke-width": w }), svg("text", { class: "lab", x: f.x1 + 6, y: Y(val) + 3 }, t));
    f.s.append(svg("path", { d: "M" + [{ n: 0, llr: 0 }, ...st].map((s) => X(s.n) + " " + Y(s.llr)).join(" L"), fill: "none", stroke: ink2, "stroke-width": 2, "stroke-linejoin": "round" }));
    const pts = st.map((s) => { f.s.append(svg("circle", { cx: X(s.n), cy: Y(s.llr), r: 4, fill: ink, stroke: panel, "stroke-width": 2 })); return { px: X(s.n), py: Y(s.llr), s }; });
    const l = st.at(-1); f.s.append(svg("text", { class: "lab", x: X(l.n) + 8, y: Y(l.llr) - 6, style: `fill:${ink}` }, "LLR " + sg(l.llr, 2)));
    if (v.flight && l.n < n) f.s.append(svg("line", { x1: X(l.n), x2: X(l.n + 1), y1: Y(l.llr), y2: Y(l.llr), stroke: cssv("--active"), "stroke-width": 2, "stroke-dasharray": "3 4" }));
    tipFor(el, pts, ({ s }) => [h("div", {}, "LLR ", h("b", {}, sg(s.llr, 2))), h("div", { class: "dim" }, `after stage ${s.n}, ${int(s.games)} games, merged ${when(s.merged)}`)]);
  }
  el = $("#ch-elo");
  if (el && el.clientWidth) {
    const f = frame(el, { l: 44, r: 84, t: 10, b: 20 }), all = st.flatMap((s) => [s.elo - (s.elo_err || 0), s.elo + (s.elo_err || 0)]).concat([0]);
    const lo = Math.min(...all) - 1, hi = Math.max(...all) + 1, X = (k) => f.x0 + (k / n) * (f.x1 - f.x0), Y = (x) => f.y1 - ((x - lo) / (hi - lo)) * (f.y1 - f.y0);
    for (let k = 1; k <= n; k++) if (n <= 9 || k % 2 === 0) f.s.append(svg("text", { x: X(k), y: f.ht - 5, "text-anchor": "middle" }, "stage " + k));
    for (const g of nice(lo, hi, 4)) f.s.append(svg("line", { x1: f.x0, x2: f.x1, y1: Y(g), y2: Y(g), stroke: g ? rule : ink3, "stroke-width": 1 }), svg("text", { x: f.x0 - 6, y: Y(g) + 3, "text-anchor": "end" }, sg(g, 0)));
    const pts = st.map((s) => { f.s.append(svg("line", { x1: X(s.n), x2: X(s.n), y1: Y(s.elo - (s.elo_err || 0)), y2: Y(s.elo + (s.elo_err || 0)), stroke: ink2, "stroke-width": 2 }), svg("circle", { cx: X(s.n), cy: Y(s.elo), r: 4, fill: ink, stroke: panel, "stroke-width": 2 })); return { px: X(s.n), py: Y(s.elo), s }; });
    const l = st.at(-1); f.s.append(svg("text", { class: "lab", x: X(l.n) + 8, y: Y(l.elo) + 3, style: `fill:${ink}` }, sg(l.elo, 2) + " ± " + (l.elo_err || 0).toFixed(2)));
    tipFor(el, pts, ({ s }) => [h("div", {}, h("b", {}, sg(s.elo, 2) + " ± " + (s.elo_err || 0).toFixed(2)), " Elo"), h("div", { class: "dim" }, `after stage ${s.n}, ${int(s.games)} games`)]);
  }
  el = $("#ch-pt");
  const pt = st.at(-1).ptnml;
  if (el && el.clientWidth && pt) {
    const f = frame(el, { l: 44, r: 84, t: 14, b: 20 }), mx = Math.max(1, ...pt), names = ["0", "½", "1", "1½", "2"], bw = Math.min(24, (f.x1 - f.x0) / 5 - 2), pts = [];
    f.s.append(svg("line", { x1: f.x0, x2: f.x1, y1: f.y1, y2: f.y1, stroke: rule }));
    pt.forEach((val, i) => {
      const cx = f.x0 + ((i + 0.5) / 5) * (f.x1 - f.x0), hh = Math.max(3, (val / mx) * (f.y1 - f.y0));
      f.s.append(svg("path", { d: `M${cx - bw / 2} ${f.y1} v${-hh + 3} q0 -3 3 -3 h${bw - 6} q3 0 3 3 v${hh - 3} Z`, fill: ink2 }), svg("text", { x: cx, y: f.y1 - hh - 4, "text-anchor": "middle" }, int(val)), svg("text", { x: cx, y: f.ht - 5, "text-anchor": "middle" }, names[i]));
      pts.push({ px: cx, py: f.y1 - hh, v: val, n: names[i] });
    });
    tipFor(el, pts, (p) => [h("div", {}, h("b", {}, int(p.v)), " pairs"), h("div", { class: "dim" }, `scored ${p.n} of 2 points for the test engine`)]);
  }
}

// ---------- situation ----------
function renderSituation() {
  const sit = S.situation || { nodes: [], edges: [], text: "" };
  if (!changed("sit", sit)) return;
  $("#now").textContent = sit.text;
  const topo = $("#topo"); topo.querySelectorAll(".col").forEach((n) => n.remove());
  for (let c = 1; c <= 5; c++) {
    const col = h("div", { class: "col" });
    for (const n of sit.nodes.filter((x) => x.col === c)) {
      const el = h("div", { class: "node " + (n.state === "active" || n.state === "failure" ? n.state : ""), id: "n-" + n.id, tabindex: 0 },
        h("div", { class: "h" }, light(n.state), n.name), h("div", { class: "state st-" + n.state }, n.word),
        h("div", { class: "n1 num" }, n.until ? h("span", { "data-until": n.until }, countdown(n.until)) : n.big), h("div", { class: "n2" }, n.until ? "to the result: " + n.small : n.small));
      el.addEventListener("click", () => focusPanel(String(n.focus)));
      col.append(el);
    }
    topo.append(col);
  }
  requestAnimationFrame(drawEdges);
}
function drawEdges() {
  const sit = (S && S.situation) || { edges: [] }, topo = $("#topo"), s = $("svg", topo), R = topo.getBoundingClientRect(); if (!R.width) return;
  s.replaceChildren(); s.setAttribute("viewBox", `0 0 ${R.width} ${R.height}`);
  const box = (id) => { const e = document.getElementById("n-" + id); if (!e) return null; const r = e.getBoundingClientRect(); return { l: r.left - R.left, r: r.right - R.left, t: r.top - R.top, b: r.bottom - R.top, cy: (r.top + r.bottom) / 2 - R.top, cx: (r.left + r.right) / 2 - R.left }; };
  for (const [a, b, st] of sit.edges) {
    const A = box(a), B = box(b); if (!A || !B) continue;
    if (Math.abs(A.cx - B.cx) < 4) { s.append(svg("path", { class: st, d: `M${A.cx} ${A.b} L${B.cx} ${B.t}` })); continue; }
    const mx = (A.r + B.l) / 2; s.append(svg("path", { class: st, d: `M${A.r} ${A.cy} C${mx} ${A.cy} ${mx} ${B.cy} ${B.l} ${B.cy}` }));
  }
  const E = box("engine"), y = R.height - 12, x = 6, gens = ["pc", "vm"].map(box).filter(Boolean);
  if (E && gens.length) {
    s.append(svg("path", { class: sit.loop_active ? "active" : "idle", d: `M${E.r} ${E.cy} h12 V${y} H${x} V${Math.min(...gens.map((g) => g.cy))}` }));
    for (const g of gens) s.append(svg("path", { class: "idle", d: `M${x} ${g.cy} H${g.l}` }));
    s.append(svg("text", { x: R.width / 2, y: y - 5, "text-anchor": "middle" }, "the default net labels new data" + (sit.labeller ? ` (labeller ${sit.labeller})` : "")));
  }
}

// ---------- alerts ----------
function renderAlerts() {
  const list = S.alerts || [];
  if (!changed("alerts", [list, [...seen]])) return;
  $("#age-alert").textContent = `${list.filter((a) => a.tier === "critical").length} critical · ${list.filter((a) => a.tier === "attention" && !seen.has(a.id)).length} to review`;
  $("#alerts").replaceChildren(...(list.length ? list.map((a) => {
    const isSeen = seen.has(a.id) || a.tier === "info", st = a.tier === "critical" ? "failure" : a.tier === "attention" ? "attention" : "idle";
    const row = h("div", { class: "alert " + a.tier + (isSeen ? " seen" : ""), title: "source: " + a.source }, light(st), h("span", { class: "what" }, a.what), h("span", { class: "when num" }, when(a.at)), h("span", { class: "why" }, a.why));
    if (a.tier === "attention" && !seen.has(a.id)) {
      const b = h("button", { title: "Dims this item in this window only. It changes nothing in the pipeline and is not saved." }, "seen");
      b.addEventListener("click", (e) => { e.stopPropagation(); seen.add(a.id); renderAlerts(); renderHealth(); });
      row.querySelector(".when").append(b);
    }
    return row;
  }) : [h("div", { class: "empty" }, "No alert. Every lane, watcher and job is as expected.")]));
}

// ---------- progress ----------
function renderProgress() {
  const o = S.overview || {};
  if (changed("prog", [o.series, o.stack, o.perf, o.adoptions, o.checks, o.decisions])) {
    const g = o.latest, ref = g && g.reference;
    $("#age-prog").textContent = g ? "last gauntlet " + when(g.at) : "no gauntlet found";
    $("#prog-title").textContent = "Gauntlet rating with its 95% interval" + (ref ? `, against ${ref.name} (${ref.rating})` : "");
    const st = h("table", {}, h("tr", {}, ...["Stacking check", "Sum of separate tests", "Measured together", "Share kept"].map((x, i) => h("th", { class: i ? "r" : "" }, x))));
    for (const s of o.stack || []) st.append(h("tr", { title: s.name }, h("td", {}, `${s.name.replace(/-stc$/, "").replace(/-/g, " ")}, ${day(s.at)}`), h("td", { class: "r num" }, s.sum == null ? "n/a" : sg(s.sum, 2)), h("td", { class: "r num" }, elo(s.elo, s.err, 2)), h("td", { class: "r num" }, s.sum ? (s.elo / s.sum).toFixed(2) : "n/a")));
    const sp = h("table", {}, h("tr", {}, ...["Speed milestones", "Change", "Measured on"].map((x) => h("th", {}, x))));
    for (const p of (o.perf || []).slice().reverse()) sp.append(h("tr", {}, h("td", { class: "num faint nw" }, p.date), h("td", { class: "num nw" }, p.change), h("td", {}, p.what)));
    const ad = h("table", {}, h("tr", {}, ...["Adopted", "Change", "Commit"].map((x) => h("th", {}, x))));
    for (const a of ((o.adoptions && o.adoptions.list) || []).slice(0, 14)) ad.append(h("tr", {}, h("td", { class: "num faint nw" }, a.date), h("td", {}, a.what), h("td", { class: "num faint" }, a.commit)));
    const ck = h("table", {}, h("tr", {}, ...["Anchor check", "Measured gain", "Outcome"].map((x) => h("th", {}, x))));
    for (const c of (o.checks || []).slice().reverse()) ck.append(h("tr", { title: "gauntlet run " + c.run }, h("td", { class: "num faint nw" }, day(c.at)), h("td", { class: "num" }, `${sg(c.gain)} (${sg(c.lo)} to ${sg(c.hi)})`), h("td", {}, h("span", { class: "sub2" }, light(c.outcome === "flagged" ? "attention" : "nominal"), c.outcome))));
    $("#prog-detail").replaceChildren(h("div", { style: "display:grid; grid-template-columns:1fr 1fr; gap:1.2rem 1.5rem; margin-top:0.6rem" }, h("div", {}, st, h("div", { style: "height:0.8rem" }), ck), h("div", {}, sp, h("div", { class: "faint", style: "font-size:0.8rem; margin-top:0.3rem" }, "No regular speed measurement exists yet: these rows come from the performance log, on differing machines.")),
      h("div", {}, ad), h("div", {}, sect("Decisions for the owner, as last written in the morning report"), (o.decisions || []).length ? (o.decisions || []).map((d) => h("p", { style: "margin:0.3rem 0; font-size:0.86rem" }, d)) : h("div", { class: "empty" }, "None found."))));
    requestAnimationFrame(drawRating);
  }
}

// ---------- training ----------
function renderTraining() {
  const T = S.training || {};
  if (!changed("train", T)) return;
  const live = (T.sessions || []).filter((s) => s.state);
  $("#age-train").textContent = live.length ? live.map((s) => `Kaggle ${s.ref}: ${s.state.toLowerCase()}`).join("; ") : T.watching ? "a Kaggle job is running" : "Kaggle: no session running";
  const out = [], q = T.quota;
  const r = (T.retrains || [])[0];
  if (r) {
    out.push(h("div", { class: "rowline" }, h("span", { style: "font-weight:600; font-size:0.95rem" }, `Retrain ${r.title}: ${r.arms.length} arm${r.arms.length > 1 ? "s" : ""}, ${r.nets} nets`), h("span", { class: "dim" }, "last change " + when(r.updated))));
    const g = h("div", { class: "pipe", style: `grid-template-columns: minmax(3.5rem, 6rem) repeat(${r.stages.length}, minmax(2.6rem, 1fr)) minmax(9rem, 15rem)` }, h("div", { class: "hd" }, "Arm"), ...r.stages.map((s) => h("div", { class: "hd" }, s)), h("div", { class: "hd", style: "justify-content:flex-end" }, "Screen Elo"));
    const keys = ["gates", "heldout", "bake", "uho", "screen", "default", "sprt"], words = { done: "done for every seed", run: "running now", wait: "waiting", none: "not run for this arm", flag: "flagged for review", fail: "failed" };
    for (const a of r.arms) {
      const scr = a.screens.slice(-2).map((s) => `${sg(s.elo)} vs ${s.against}`).join(", ");
      g.append(h("div", { class: "arm", title: a.tip }, a.arm || a.nets[0], a.promoted ? h("span", { class: "chip" }, "default") : null), ...keys.map((k, i) => h("div", { class: "c", title: `${r.stages[i]}: ${words[a.cells[k]] || a.cells[k]}` }, h("span", { class: "cell " + a.cells[k] }))),
        h("div", { class: "res num", title: a.screens.map((s) => `seed ${s.seed}: ${sg(s.elo)} ± ${s.err} against ${s.against}`).join("\n") }, scr));
    }
    out.push(g, h("div", { class: "legend" }, ...[["done", "passed"], ["run", "running"], ["wait", "waiting"], ["flag", "flagged"], ["fail", "failed"], ["none", "not run"]].map(([c, t]) => h("span", {}, h("span", { class: "cell " + c }), t))));
  } else out.push(h("div", { class: "empty" }, "No retrain with gate results was found."));
  out.push(h("hr"));
  if (q) out.push(h("div", { class: "meter" }, h("span", {}, "Kaggle GPU quota: ", h("span", { class: "num" }, q.left.toFixed(1) + " h left"), ` of ${q.total.toFixed(0)} h`), h("span", { class: "faint", style: "font-size:0.78rem" }, `as of ${when(q.at)}, the last session's end; resets ${when(q.reset)}`),
    h("div", { class: "bar" }, h("i", { style: `width:${(q.used / q.total) * 100}%` }))));
  const rest = [];
  for (const p of T.prep || []) rest.push(light(p.live === false ? "attention" : "active"), h("span", { title: `job ${p.name}, type ${p.type}` }, `Job ${p.name}`, h("span", { class: "dim" }, ` · running since ${when(p.started)}`)));
  for (const s of T.sessions || []) rest.push(light(s.state === "RUNNING" ? "active" : s.state ? "nominal" : "attention"), h("span", {}, `Kaggle session ${s.ref}`, h("span", { class: "dim" }, ` · ${s.state ? s.state.toLowerCase() : "state not read: " + s.error}, checked ${when(s.at)}`)));
  for (const x of (T.retrains || []).slice(1)) rest.push(light("nominal"), h("span", {}, `Retrain ${x.title}`, h("span", { class: "dim" }, ` · ${x.nets} nets, last change ${when(x.updated)}` + (x.arms.some((a) => a.promoted) ? ", holds the default net" : ""))));
  for (const x of T.others || []) rest.push(light(x.state), h("span", {}, x.name, h("span", { class: "dim" }, ` · ${x.text}, ${when(x.at)}`)));
  if (rest.length) out.push(sect("Sessions, jobs and earlier retrains"), h("div", { class: "list" }, rest));
  $("#train").replaceChildren(...out);
}

// ---------- data ----------
function renderData() {
  const D = S.data || {};
  if (!changed("data", D)) return;
  const vm = D.vm, pc = D.pc, rows = [], n = now();
  $("#age-data").textContent = vm && vm.status_at ? "VM status " + span(n - vm.status_at) + " old" : "";
  if (vm) {
    const gen = vm.status === "RUNNING" && vm.running;
    rows.push(light(gen ? "active" : vm.status === "RUNNING" ? "idle" : "attention"), h("span", { title: `${vm.machine_type}, ${vm.provisioning}; wanted ${vm.wanted || "unknown"}` }, h("b", {}, "Cloud VM "), gen ? `running ${vm.running} since ${when(vm.since)}` : String(vm.status).toLowerCase(),
      h("div", { class: "dim" }, vm.rate_est ? [h("span", { class: "num" }, "~" + pos(vm.rate_est)), " positions / h, estimated from the last full run; "] : gen ? "rate not recorded; " : "", h("span", { class: "num" }, pos(vm.verified)), ` verified on the PC in ${int(vm.chunks)} chunks`,
        vm.unpulled_est ? ["; about ", h("span", { class: "num" }, pos(vm.unpulled_est)), " not yet pulled"] : "", vm.cost_est != null ? ["; about ", h("span", { class: "num" }, "$" + vm.cost_est.toFixed(2)), ` since ${when(vm.last_start)}`] : "")));
  } else rows.push(light("idle"), h("span", {}, h("b", {}, "Cloud VM "), "no status file found"));
  if (pc) {
    const on = pc.state === "active";
    rows.push(light(on ? "active" : "idle"), h("span", {}, h("b", {}, "PC "), on ? `generating part ${pc.part}` : pc.since ? `idle since ${when(pc.since)}` : "idle",
      h("div", { class: "dim" }, on ? (pc.positions != null ? [h("span", { class: "num" }, pos(pc.positions)), pc.target ? ` of ${pos(pc.target)}` : "", " positions; ", h("span", { class: "num" }, pos(pc.rate)), " / h over the last hour"] : pc.note || "")
        : pc.part ? [`last part ${pc.part}: `, h("span", { class: "num" }, pos(pc.last_positions)), " positions", pc.seal ? `, ${pc.seal}` + (pc.seal_at ? " " + when(pc.seal_at) : "") : ""] : "no part recorded")));
  }
  if (D.arms) rows.push(light("active"), h("span", {}, h("b", {}, "Arms "), `job ${D.arms.job}, ${D.arms.live} live`, h("div", { class: "dim num" }, Object.entries(D.arms.arms).map(([k, v]) => `${k} ${pos(v)}`).join("; "))));
  const labs = D.labellers || [], mx = Math.max(1, ...labs.map((l) => l.positions)), cur = (S.overview || {}).net, rk = h("div", { class: "rank" });
  for (const l of labs) rk.append(h("span", { class: l.name === cur ? "" : "dim", title: "data labelled by net " + l.name }, l.name), h("span", {}, h("span", { class: "b" + (l.name === cur ? " cur" : ""), style: `width:${(l.positions / mx) * 100}%`, title: `${int(l.positions)} positions` })), h("span", { class: "num", style: "text-align:right" }, pos(l.positions)));
  $("#data").replaceChildren(h("div", { class: "list" }, rows), sect("Positions by labeller, oldest first", pos(D.total) + " in " + (D.parts || 0) + " parts"), labs.length ? rk : h("div", { class: "empty" }, "No data manifest was found."));
}

// ---------- machine ----------
function renderMachine() {
  const M = S.machine || {};
  const struct = [M.threads, M.mem_total, M.freeze, M.wsl, M.memwatch, M.compile, M.nps_lock, S.jobs, (M.hist || {}).cpu && M.hist.cpu.length];
  if (changed("mach", struct)) {
    const tile = (label, id, unit, hist, sub) => h("div", { class: "tile" }, h("div", { class: "lbl" }, label), h("div", { class: "v num" }, h("span", { id }), h("small", {}, unit), spark(hist)), h("div", { class: "s" }, sub));
    const w = M.wsl, fz = M.freeze || {}, mw = M.memwatch, cp = M.compile || {}, jobs = (S.jobs && S.jobs.running) || [], hist = M.hist || {};
    const lastDrop = w && w.drops && w.drops.length ? w.drops.at(-1) : null;
    const facts = [light(fz.stalls ? "attention" : fz.since ? "nominal" : "idle"), h("span", {}, "Freeze monitor: ", fz.since ? [h("span", { class: "num" }, fz.stalls), ` stall${fz.stalls === 1 ? "" : "s"} recorded` + (fz.last ? `; last check ${when(fz.last.at)}` : "")] : "no log found"),
      light(mw && mw.actions.length ? "attention" : mw ? "nominal" : "idle"), h("span", {}, "Memory watch: ", mw ? (mw.actions.length ? `last action ${when(mw.actions.at(-1).at)}` : `no action since it started ${when(mw.started)}`) : "no log found"),
      light(cp.state === "held" ? "active" : "idle"), h("span", { title: cp.text || "" }, "Compile lock: ", cp.state === "lifted" ? `lifted since ${when(cp.at)}` : cp.state === "held" ? `held (${cp.text})` + (cp.queue.length ? `, ${cp.queue.length} waiting` : "") : "free", cp.waited_today ? `; ${span(cp.waited_today)} waited today` : ""),
      ...(M.nps_lock || []).flatMap((x) => [light("active"), h("span", {}, "Speed measurement lock: held by ", x.who, " since ", when(x.at))]),
      light(jobs.some((j) => j.live === false) ? "attention" : "active"), h("span", { title: jobs.map((j) => `${j.name} (${j.type}) since ${when(j.started)}` + (j.live === false ? ", no live process" : "")).join("\n") }, h("span", { class: "num" }, jobs.length), " supervised jobs running: ", jobs.map((j) => j.name).join(", "))];
    $("#mach").replaceChildren(h("div", { class: "tiles" }, tile("CPU load", "m-cpu", "%", hist.cpu, `${M.threads || "?"} threads; trend since the display started`), tile("Memory available", "m-avail", "GB", hist.avail, M.mem_total ? `of ${(M.mem_total / 2 ** 30).toFixed(0)} GB` : ""),
      tile("Commit charge", "m-commit", "%", hist.commit, fz.last ? `freeze monitor read ${fz.last.commit}% at ${when(fz.last.at)}` : ""), tile("WSL cache", "m-wsl", "MB", w && w.drops ? w.drops.slice(-8).map((d) => d.before) : null, w ? (lastDrop ? `dropped ${when(lastDrop.at)}; ` : "") + (w.limit_mb ? `limit ${int(w.limit_mb)} MB` : "") : "no log found")), h("hr"), h("div", { class: "list" }, facts));
  }
  const set = (id, t) => { const e = document.getElementById(id); if (e && e.textContent !== t) e.textContent = t; };
  set("m-cpu", M.cpu == null ? "n/a" : M.cpu.toFixed(0)); set("m-avail", M.mem_avail == null ? "n/a" : (M.mem_avail / 2 ** 30).toFixed(2));
  set("m-commit", M.commit == null ? "n/a" : M.commit.toFixed(0)); set("m-wsl", M.wsl && M.wsl.cache_mb != null ? int(M.wsl.cache_mb) : "n/a");
}

// ---------- ticker, sources ----------
function renderTicker() {
  const ev = S.events || [];
  if (!changed("ticker", ev)) return;
  const mk = () => ev.map((e) => h("span", { class: "ev" }, h("span", { class: "tm num" }, when(e.at)), light(e.state), e.text));
  $("#tick-run").replaceChildren(...mk(), ...mk());
  $("#tick-run").style.animationDuration = Math.max(60, ev.length * 9) + "s";
}
function renderSources() {
  const H = S.health || { failing: {} }, D = S.display || {}, f = Object.entries(H.failing || {});
  $("#s-display").textContent = `display only · ${H.sources || 0} sources read, ${f.length} failing` + (D.busy_percent != null ? ` · uses ${D.busy_percent}% of one core` : "");
  if (!changed("sources", [H, D.net])) return;
  $("#sources").replaceChildren(h("h3", {}, "Sources"), h("p", {}, `${H.sources || 0} files and folders are read, each only when it changes. A source that fails keeps its last good value on screen and is listed here.`),
    f.length ? h("div", { class: "list" }, f.flatMap(([k, v]) => [light("attention"), h("span", {}, k, h("div", { class: "dim" }, v.error || "unreadable"))])) : h("p", {}, "Every source reads as expected."),
    h("h3", {}, "Network polls"), h("div", { class: "list" }, [light(/^ok|^idle/.test((D.net || {}).gh || "") ? "nominal" : "idle"), h("span", {}, "GitHub (shards of the live runs, every 2 minutes): ", (D.net || {}).gh || "off"),
      light(/^ok|^idle/.test((D.net || {}).kaggle || "") ? "nominal" : "idle"), h("span", {}, "Kaggle (session state, every 5 minutes, only while a session job runs): ", (D.net || {}).kaggle || "off")]),
    h("h3", {}, "This display"), h("p", {}, `Running for ${span(D.uptime || 0)}. It writes no file and starts no job.`));
}

// ---------- loop ----------
function tick() {
  if (!S) return;
  const n = now();
  $("#c-time").textContent = hm(n, true) + " EST";
  const d = est(n), age = Date.now() / 1000 - lastOk;
  $("#c-date").textContent = `${DAYS[d.getUTCDay()]}, ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()} · updated ${Math.max(0, Math.round(age))} s ago`;
  document.querySelectorAll("[data-until]").forEach((e) => { const t = countdown(+e.dataset.until); if (e.textContent !== t) e.textContent = t; });
  const stale = $("#stale");
  if (age > 15) { stale.style.display = "block"; stale.textContent = `The display's server has not answered for ${span(age)}. What is shown is as of ${hm(lastOk + skew / 1000)}.`; } else stale.style.display = "none";
}
function render() {
  if (S.fatal) { $("#stale").style.display = "block"; $("#stale").textContent = "The display's collector failed: " + S.fatal; return; }
  for (const fn of [renderStrip, renderTesting, renderSituation, renderAlerts, renderProgress, renderTraining, renderData, renderMachine, renderTicker, renderSources, renderHealth]) {
    try { fn(); } catch (e) { console.error(fn.name, e); }
  }
  tick();
}
async function poll() {
  try {
    const r = await fetch("/snapshot", { cache: "no-store" });
    if (!r.ok) return;
    const snap = await r.json();
    if (!snap || !snap.now) return;
    S = snap; lastOk = Date.now() / 1000; skew = snap.now * 1000 - Date.now();
    const web = snap.display && snap.display.web;
    if (webVersion != null && web && web !== webVersion) { location.reload(); return; }
    if (web) webVersion = web;
    render();
  } catch (e) { /* the server is away: tick() shows the notice */ }
}
function focusPanel(key) {
  const main = $("#main"), p = document.querySelector(`.panel[data-key="${key}"]`);
  document.querySelectorAll(".panel.focused").forEach((x) => x.classList.remove("focused"));
  if (p && main.dataset.focus !== key) { main.classList.add("focus"); p.classList.add("focused"); main.dataset.focus = key; }
  else { main.classList.remove("focus"); delete main.dataset.focus; }
  requestAnimationFrame(redraw);
}
function redraw() { drawRating(); drawLaneCharts(); drawEdges(); }
document.querySelectorAll(".panel > header").forEach((hd) => hd.addEventListener("click", () => focusPanel(hd.parentElement.dataset.key)));
$("#b-theme").addEventListener("click", () => { document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; requestAnimationFrame(redraw); });
$("#b-help").addEventListener("click", () => { $("#help").classList.toggle("open"); $("#sources").classList.remove("open"); });
$("#b-src").addEventListener("click", () => { $("#sources").classList.toggle("open"); $("#help").classList.remove("open"); });
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.key >= "1" && e.key <= "7") focusPanel(e.key);
  else if (e.key === "Escape") { if ($("#main").dataset.focus) focusPanel($("#main").dataset.focus); $("#help").classList.remove("open"); $("#sources").classList.remove("open"); }
  else if (e.key === "t" || e.key === "T") $("#b-theme").click();
  else if (e.key === "s" || e.key === "S") $("#b-src").click();
  else if (e.key === "?") $("#b-help").click();
});
window.addEventListener("resize", () => requestAnimationFrame(redraw));
const hash = location.hash;
if (/theme=light/.test(hash)) document.documentElement.dataset.theme = "light";
poll().then(() => { const fm = /focus=(\d)/.exec(hash); if (fm) focusPanel(fm[1]); });
setInterval(poll, 2000); setInterval(tick, 1000);
