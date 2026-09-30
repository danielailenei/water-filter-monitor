/* Water Filter Monitor - dashboard.
 * Polls the FastAPI backend on the same origin (no CORS, no dependencies, no
 * build step): latest reading + prediction every 5 s, history + alerts every 30 s. */

const POLL_MS = 5000;
const SLOW_EVERY = 6;           // history + alerts once every N polls
const PREDICT_HOURS = 6;        // window sent to /predict; the model keeps only the current cycle
const CYCLE_RESET_DROP = 0.3;   // same rules as backend/ml_model.py current_cycle():
const CYCLE_RESET_GAP_MS = 600 * 1000; //   pressure drop or a gap in the data starts a new cycle
const STALE_AFTER_S = 30;       // no new reading for this long -> "fără date noi"
const MAX_CHART_POINTS = 800;   // decimate long ranges so the SVG stays light

/* New-filter values (sensor/config.yaml) - the deltas are shown against these. */
const BASE = { pressure: 0.2, flow: 15.0, turbidity: 0.5 };

const METRICS = {
  pressure: { key: "pressure_drop_bar", label: "Presiune", unit: "bar", digits: 3 },
  flow: { key: "flow_rate_lmin", label: "Debit", unit: "L/min", digits: 2 },
  turbidity: { key: "turbidity_ntu", label: "Turbiditate", unit: "NTU", digits: 2 },
};

const state = {
  threshold: 1.5,
  latest: null,
  prev: null,
  predict: null,
  predictAt: 0,          // when /predict answered (ms), for the live countdown
  readings: [],          // /history rows
  metric: "pressure",
  hours: 1,
  cycleOnly: true,
  lastDataAt: null,      // time of the newest reading (Date)
  tick: 0,
  error: false,
};

const $ = (id) => document.getElementById(id);

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

/* ---------------- formatting ---------------- */

const isNum = (n) => typeof n === "number" && Number.isFinite(n);
const fmt = (n, digits = 2) => (isNum(n) ? n.toFixed(digits) : "–");

function fmtDuration(secs) {
  if (!isNum(secs)) return "–";
  const s = Math.max(0, Math.round(secs));
  if (s < 90) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 90) return `${m} min`;
  const h = Math.floor(s / 3600);
  const mm = Math.round((s % 3600) / 60);
  if (h < 48) return mm ? `${h} h ${mm} min` : `${h} h`;
  return `${(s / 86400).toFixed(1)} zile`;
}

/* Dates/times: the API sends UTC (ISO 8601); everything is shown in Romanian
 * time and format, the same as the alert emails, whatever the viewer's clock. */
const TZ = "Europe/Bucharest";
const dayKey = (d) => d.toLocaleDateString("ro-RO", { timeZone: TZ });
const isToday = (d) => dayKey(d) === dayKey(new Date());

const fmtClock = (d, seconds = false) =>
  d.toLocaleTimeString("ro-RO", {
    timeZone: TZ, hour: "2-digit", minute: "2-digit", second: seconds ? "2-digit" : undefined,
  });

const fmtDay = (d) => d.toLocaleDateString("ro-RO", { timeZone: TZ, day: "2-digit", month: "2-digit" });

// full: 30.09.2026, 13:08:26 (tooltips)
const fmtFull = (d) =>
  d.toLocaleString("ro-RO", {
    timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

// only the time today, "29.09, 13:08" on other days
const fmtWhen = (d, seconds = false) => (isToday(d) ? fmtClock(d, seconds) : `${fmtDay(d)}, ${fmtClock(d, seconds)}`);

const agoSeconds = (d) => (Date.now() - d.getTime()) / 1000;

/* ---------------- status ---------------- */

function setConn(stateName, text) {
  const el = $("conn");
  el.dataset.state = stateName;
  el.textContent = text;
}

function refreshStatus() {
  if (state.error) return setConn("error", "eroare conexiune");
  if (!state.lastDataAt) return setConn("stale", "fără date");
  const age = agoSeconds(state.lastDataAt);
  $("updated").textContent = `ultima citire acum ${fmtDuration(age)}`;
  $("updated").title = fmtFull(state.lastDataAt);
  if (age > STALE_AFTER_S) setConn("stale", "fără date noi");
  else setConn("ok", "live");
}

/* Filter condition from the clogging percentage (pressure / threshold). */
function level(pct) {
  if (pct >= 100) return { level: "danger", text: "înfundat — necesită înlocuire" };
  if (pct >= 90) return { level: "danger", text: "critic" };
  if (pct >= 80) return { level: "warn", text: "atenție — pregătește un filtru nou" };
  return { level: "ok", text: "în stare bună" };
}

/* ---------------- latest reading ---------------- */

function renderLatest() {
  const r = state.latest;
  if (!r) {
    $("state-chip").textContent = "aștept date de la senzor…";
    return;
  }
  const p = r.pressure_drop_bar;
  const pct = (p / state.threshold) * 100;

  // gauge
  const CIRC = 2 * Math.PI * 80;
  const fg = $("gauge-fg");
  const lv = level(pct);
  fg.style.strokeDashoffset = CIRC * (1 - Math.min(Math.max(pct, 0), 100) / 100);
  fg.style.stroke = `var(--${lv.level})`;
  $("clog-pct").textContent = Math.round(pct);
  $("state-chip").textContent = lv.text;
  $("state-chip").dataset.level = lv.level;
  $("pressure-vs-threshold").textContent = `${fmt(p, 3)} / ${fmt(state.threshold, 1)} bar`;

  // metrics: value, change since the previous reading, difference to a new filter
  const rows = [
    ["m-pressure", "pressure", BASE.pressure],
    ["m-flow", "flow", BASE.flow],
    ["m-turb", "turbidity", BASE.turbidity],
  ];
  for (const [id, metric, base] of rows) {
    const m = METRICS[metric];
    const v = r[m.key];
    $(id).textContent = fmt(v, m.digits);
    const d = v - base;
    $(`${id}-delta`).textContent = isNum(v)
      ? `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(2)} ${m.unit} față de un filtru nou`
      : " ";
    const trend = $(`${id}-trend`);
    const before = state.prev && state.prev[m.key];
    if (isNum(v) && isNum(before) && Math.abs(v - before) > 0.005) {
      trend.textContent = v > before ? "▲" : "▼";
      trend.dataset.dir = v > before ? "up" : "down";
      trend.title = `${v > before ? "+" : ""}${(v - before).toFixed(3)} față de citirea anterioară`;
    } else {
      trend.textContent = "•";
      trend.dataset.dir = "flat";
      trend.title = "fără schimbare";
    }
  }
}

/* ---------------- prediction ---------------- */

function renderPredict() {
  const d = state.predict;
  const r = state.latest;
  if (!d) return;
  const since = (Date.now() - state.predictAt) / 1000; // live countdown between polls
  const main = $("predict-main");
  const sub = $("predict-sub");
  const box = main.parentElement;

  // No reading in the last 10 minutes: the fit would describe stale data
  if (!r) {
    main.textContent = "fără date recente";
    sub.textContent = "senzorul nu a trimis citiri în ultimele 10 minute";
    box.dataset.level = "";
    for (const id of ["pred-ml", "pred-model", "pred-r2", "pred-rate"]) $(id).textContent = "–";
    $("cycle-start").textContent = "–";
    return;
  }

  if (d.status === "clogged") {
    main.textContent = "înfundat";
    sub.textContent = `pragul a fost atins acum ${fmtDuration(d.seconds_since_clogged + since)}`;
    box.dataset.level = "danger";
  } else if (d.status === "ok") {
    const left = d.seconds_remaining - since;
    main.textContent = left > 0 ? `în ${fmtDuration(left)}` : "iminent";
    sub.textContent = `până la pragul de ${fmt(state.threshold, 1)} bar`;
    box.dataset.level = left < 300 ? "danger" : left < 1800 ? "warn" : "ok";
  } else if (d.status === "stable") {
    main.textContent = "stabil";
    sub.textContent = "presiunea nu crește în ciclul curent";
    box.dataset.level = "ok";
  } else {
    main.textContent = "calculez…";
    sub.textContent = `aștept cel puțin 5 citiri în ciclul curent (acum ${d.cycle_points || 0})`;
    box.dataset.level = "";
  }

  // regression vs the simulator's analytic estimate
  if (d.status === "ok") $("pred-ml").textContent = `în ${fmtDuration(d.seconds_remaining - since)}`;
  else if (d.status === "clogged" && d.clogged_at) $("pred-ml").textContent = `prag atins la ${fmtWhen(new Date(d.clogged_at))}`;
  else if (d.status === "stable") $("pred-ml").textContent = "fără trend crescător";
  else $("pred-ml").textContent = "prea puține citiri";

  const modelDays = r && r.days_remaining_model;
  if (isNum(modelDays)) {
    $("pred-model").textContent = modelDays <= 0 ? "prag atins" : `în ${fmtDuration(modelDays * 86400)}`;
  } else {
    $("pred-model").textContent = "indisponibil";
  }

  if (isNum(d.r_squared)) {
    const q = d.r_squared >= 0.95 ? "excelent" : d.r_squared >= 0.8 ? "bun" : "slab";
    $("pred-r2").textContent = `${d.r_squared.toFixed(3)} · ${q} (${d.points_used} puncte)`;
  } else {
    $("pred-r2").textContent = "n/a — prea puține puncte";
  }

  // k from ln(p) = k*t + b, per hour -> the time in which the pressure doubles
  const k = d.degradation_rate_per_hour;
  $("pred-rate").textContent = isNum(k) && k > 0
    ? `presiunea se dublează la ~${fmtDuration((Math.LN2 / k) * 3600)}`
    : "–";

  $("cycle-start").textContent = d.cycle_started_at
    ? `${fmtWhen(new Date(d.cycle_started_at))} (acum ${fmtDuration(agoSeconds(new Date(d.cycle_started_at)))})`
    : "–";
}

/* ---------------- history chart ---------------- */

function chartSeries() {
  let rows = state.readings.filter((r) => isNum(r.pressure_drop_bar));
  let hidden = 0;
  if (state.cycleOnly) {
    let start = 0;
    for (let i = 1; i < rows.length; i++) {
      const dropped = rows[i - 1].pressure_drop_bar - rows[i].pressure_drop_bar > CYCLE_RESET_DROP;
      const gap = new Date(rows[i].time) - new Date(rows[i - 1].time) > CYCLE_RESET_GAP_MS;
      if (dropped || gap) start = i;
    }
    hidden = start;
    rows = rows.slice(start);
  }
  const key = METRICS[state.metric].key;
  let pts = rows.filter((r) => isNum(r[key])).map((r) => ({ t: new Date(r.time), v: r[key] }));
  if (pts.length > MAX_CHART_POINTS) {
    const step = pts.length / MAX_CHART_POINTS;
    pts = Array.from({ length: MAX_CHART_POINTS }, (_, i) => pts[Math.floor(i * step)]).concat(pts[pts.length - 1]);
  }
  return { pts, hidden, total: rows.length };
}

let chartGeom = null; // kept for the hover handler

function drawChart() {
  const svg = $("chart");
  const { pts, hidden, total } = chartSeries();
  const m = METRICS[state.metric];
  svg.innerHTML = "";
  $("tooltip").hidden = true;
  chartGeom = null;

  if (pts.length < 2) {
    $("chart-note").textContent = "date insuficiente pentru grafic în intervalul ales";
    return;
  }

  const W = svg.clientWidth || 600;
  const H = svg.clientHeight || 240;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const pad = { l: 48, r: 14, t: 12, b: 26 };

  const values = pts.map((p) => p.v);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (state.metric === "pressure") max = Math.max(max, state.threshold);
  const span = max - min || 1;
  min = Math.max(0, min - span * 0.05); // no measured quantity here can be negative
  max += span * 0.08;

  const t0 = pts[0].t.getTime();
  const t1 = pts[pts.length - 1].t.getTime();
  const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * (W - pad.l - pad.r);
  const y = (v) => H - pad.b - ((v - min) / (max - min)) * (H - pad.t - pad.b);

  const ns = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs, text) => {
    const el = document.createElementNS(ns, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (text !== undefined) el.textContent = text;
    svg.appendChild(el);
    return el;
  };

  // horizontal grid + value labels
  for (let i = 0; i <= 4; i++) {
    const v = min + ((max - min) * i) / 4;
    const yy = y(v);
    mk("line", { class: "grid", x1: pad.l, x2: W - pad.r, y1: yy, y2: yy });
    mk("text", { class: "axis", x: pad.l - 6, y: yy + 4, "text-anchor": "end" }, v.toFixed(m.digits > 2 ? 2 : 1));
  }
  // time labels: seconds on short ranges (otherwise they repeat), the date when
  // the range spans more than one day
  const withSeconds = t1 - t0 < 10 * 60 * 1000;
  const withDate = dayKey(new Date(t0)) !== dayKey(new Date(t1));
  for (let i = 0; i <= 4; i++) {
    const t = new Date(t0 + ((t1 - t0) * i) / 4);
    const anchor = i === 0 ? "start" : i === 4 ? "end" : "middle";
    const label = withDate ? `${fmtDay(t)} ${fmtClock(t)}` : fmtClock(t, withSeconds);
    mk("text", { class: "axis", x: x(t.getTime()), y: H - 6, "text-anchor": anchor }, label);
  }

  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t.getTime()).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  mk("path", { class: "area", d: `${line}L${x(t1).toFixed(1)},${H - pad.b}L${x(t0).toFixed(1)},${H - pad.b}Z` });
  mk("path", { class: "line", d: line });

  if (state.metric === "pressure") {
    const ty = y(state.threshold);
    mk("line", { class: "threshold", x1: pad.l, x2: W - pad.r, y1: ty, y2: ty });
    mk("text", { class: "threshold-label", x: W - pad.r - 4, y: ty - 5, "text-anchor": "end" },
       `prag înfundare ${fmt(state.threshold, 1)} bar`);
  }

  const cursor = mk("line", { class: "cursor", y1: pad.t, y2: H - pad.b, visibility: "hidden" });
  const dot = mk("circle", { class: "dot", r: 4, visibility: "hidden" });
  chartGeom = { pts, x, y, cursor, dot, W, pad, unit: m.unit, digits: m.digits, label: m.label };

  const first = pts[0].t;
  const last = pts[pts.length - 1].t;
  $("chart-note").textContent =
    `${total} citiri · ${fmtWhen(first)} – ${fmtWhen(last)}` +
    (hidden > 0 ? ` · ${hidden} citiri din cicluri anterioare ascunse` : "");
}

function onChartMove(ev) {
  if (!chartGeom) return;
  const svg = $("chart");
  const rect = svg.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const { pts, x, y, cursor, dot } = chartGeom;
  // nearest point by x (points are sorted by time)
  let lo = 0;
  let hi = pts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (x(pts[mid].t.getTime()) < mx) lo = mid; else hi = mid;
  }
  const p = Math.abs(x(pts[lo].t.getTime()) - mx) < Math.abs(x(pts[hi].t.getTime()) - mx) ? pts[lo] : pts[hi];
  const px = x(p.t.getTime());
  const py = y(p.v);
  cursor.setAttribute("x1", px);
  cursor.setAttribute("x2", px);
  cursor.setAttribute("visibility", "visible");
  dot.setAttribute("cx", px);
  dot.setAttribute("cy", py);
  dot.setAttribute("visibility", "visible");
  const tip = $("tooltip");
  tip.innerHTML = `<b>${p.v.toFixed(chartGeom.digits)} ${chartGeom.unit}</b>${fmtFull(p.t)}`;
  tip.style.left = `${Math.min(Math.max(px, 60), rect.width - 60)}px`;
  tip.style.top = `${py}px`;
  tip.hidden = false;
}

function onChartLeave() {
  if (!chartGeom) return;
  chartGeom.cursor.setAttribute("visibility", "hidden");
  chartGeom.dot.setAttribute("visibility", "hidden");
  $("tooltip").hidden = true;
}

/* ---------------- alerts ---------------- */

const ALERT_TEXT = {
  80: ["⚠️", "80% din pragul de înfundare — email + push trimise"],
  90: ["🟠", "90% din pragul de înfundare — email + push trimise"],
  100: ["🔴", "filtru înfundat — email + push trimise"],
};

function renderAlerts(events) {
  const ul = $("alerts");
  ul.innerHTML = "";
  if (!events.length) {
    ul.innerHTML = '<li class="muted">nicio alertă în ultimele 24 h</li>';
    return;
  }
  for (const e of events) {
    const [icon, text] = e.kind === "reset"
      ? ["🔄", "filtru nou (presiune scăzută) — praguri reactivate"]
      : ALERT_TEXT[e.threshold] || ["⚠️", `prag ${e.threshold}%`];
    const li = document.createElement("li");
    const t = new Date(e.time);
    li.innerHTML = `<time title="${fmtFull(t)}">${fmtWhen(t, true)}</time><span>${icon}</span><span></span>`;
    li.lastChild.textContent = text;
    ul.appendChild(li);
  }
}

/* ---------------- polling ---------------- */

async function pollFast() {
  const [predict, latest] = await Promise.all([
    getJSON(`/predict?hours=${PREDICT_HOURS}`),
    getJSON("/latest"),
  ]);
  if (isNum(predict.clog_threshold_bar)) state.threshold = predict.clog_threshold_bar;
  state.predict = predict;
  state.predictAt = Date.now();
  if (latest.status === "no_data") {
    state.latest = null;
  } else {
    if (!state.latest || state.latest.time !== latest.time) state.prev = state.latest;
    state.latest = latest;
    state.lastDataAt = new Date(latest.time);
  }
  renderLatest();
  renderPredict();
}

async function pollSlow() {
  const [history, alerts] = await Promise.all([
    getJSON(`/history?hours=${state.hours}`),
    getJSON("/alerts?hours=24"),
  ]);
  state.readings = history.readings || [];
  drawChart();
  renderAlerts(alerts.events || []);
}

async function poll() {
  try {
    await pollFast();
    if (state.tick % SLOW_EVERY === 0) await pollSlow();
    state.error = false;
  } catch (err) {
    state.error = true;
    console.error(err);
  } finally {
    state.tick++;
    refreshStatus();
  }
}

/* ---------------- interaction ---------------- */

function selectMetric(metric) {
  state.metric = metric;
  for (const b of $("metric-tabs").children) b.classList.toggle("active", b.dataset.metric === metric);
  for (const row of document.querySelectorAll(".metric")) row.classList.toggle("active", row.dataset.metric === metric);
  drawChart();
}

$("metric-tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-metric]");
  if (b) selectMetric(b.dataset.metric);
});

for (const row of document.querySelectorAll(".metric")) {
  row.addEventListener("click", () => {
    selectMetric(row.dataset.metric);
    $("chart").scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

$("range-buttons").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-h]");
  if (!b) return;
  state.hours = parseFloat(b.dataset.h);
  for (const x of $("range-buttons").children) x.classList.toggle("active", x === b);
  $("chart-note").textContent = "se încarcă…";
  getJSON(`/history?hours=${state.hours}`)
    .then((h) => { state.readings = h.readings || []; drawChart(); })
    .catch((err) => console.error(err));
});

$("cycle-only").addEventListener("change", (e) => {
  state.cycleOnly = e.target.checked;
  drawChart();
});

$("chart").addEventListener("mousemove", onChartMove);
$("chart").addEventListener("mouseleave", onChartLeave);
window.addEventListener("resize", () => drawChart());

/* The Grafana address depends on where the stack runs (localhost:3000 with
 * docker compose, /grafana/ behind CloudFront on AWS) - the backend knows it. */
getJSON("/config")
  .then((cfg) => { $("grafana-link").href = cfg.grafana_url; })
  .catch((err) => console.error(err));

selectMetric("pressure");
poll();
setInterval(poll, POLL_MS);
// between polls: live countdown and "ultima citire acum X s"
setInterval(() => { renderPredict(); refreshStatus(); }, 1000);
