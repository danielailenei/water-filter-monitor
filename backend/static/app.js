/* Water Filter Monitor - minimal dashboard.
 * Polls the FastAPI backend on the same origin every 5 s (the virtual sensor
 * publishes at that rate). No dependencies, no build step. */

const POLL_MS = 5000;
const HISTORY_EVERY = 6; // refetch /history once every N polls
const PREDICT_HOURS = 2; // fixed window fed to /predict (kept clean for the fit)

let historyHours = 1; // /history window, changed by the range buttons

/* Fresh-filter baseline values - see sensor/config.yaml (simulation.*).
 * CLOG_THRESHOLD_FALLBACK is used until /predict reports the real threshold. */
const BASE = { pressure: 0.2, flow: 15.0, turbidity: 0.5 };
const CLOG_THRESHOLD_FALLBACK = 1.5;

let tick = 0;
let clogThreshold = CLOG_THRESHOLD_FALLBACK;
let lastReading = null;

const $ = (id) => document.getElementById(id);

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function setConn(state, text) {
  const el = $("conn");
  el.dataset.state = state;
  el.textContent = text;
}

function fmt(n, digits = 2) {
  return n === null || n === undefined || Number.isNaN(Number(n))
    ? "–"
    : Number(n).toFixed(digits);
}

/* Time-to-clog, in seconds, shown in the largest unit that reads naturally.
 * With the sped-up simulation this is often only minutes. */
function formatRemaining(secs) {
  if (secs === null || secs === undefined || Number.isNaN(Number(secs))) return "–";
  const s = Number(secs);
  if (s <= 0) return "acum";
  if (s >= 2 * 86400) return `${(s / 86400).toFixed(1)} zile`;
  if (s >= 2 * 3600) return `${(s / 3600).toFixed(1)} ore`;
  if (s >= 90) return `${Math.round(s / 60)} min`;
  return `${Math.round(s)} s`;
}

function deltaText(current, base) {
  if (current === null || current === undefined) return "—";
  const d = current - base;
  const sign = d >= 0 ? "+" : "−";
  return `${sign}${Math.abs(d).toFixed(2)} vs nou`;
}

function updateGauge(pct) {
  const CIRC = 2 * Math.PI * 80;
  const clamped = Math.max(0, Math.min(pct, 100));
  const fg = $("gauge-fg");
  fg.style.strokeDashoffset = CIRC * (1 - clamped / 100);
  fg.style.stroke =
    pct >= 90 ? "var(--danger)" : pct >= 80 ? "var(--warn)" : "var(--ok)";
  // The simulator's pressure keeps rising past the threshold (no auto-reset),
  // so pct can exceed 100. A "clogging %" over 100 is meaningless and the ring
  // is already full - cap the readout at 100 and switch the label to a state.
  $("clog-pct").textContent = Math.min(Math.round(pct), 100);
  $("clog-word").textContent = pct >= 100 ? "înfundat" : "înfundare";
}

async function pollPredict() {
  const data = await getJSON(`/predict?hours=${PREDICT_HOURS}`);
  if (typeof data.clog_threshold_bar === "number") {
    clogThreshold = data.clog_threshold_bar;
  }
  if (data.status === "ok") {
    const secs =
      typeof data.seconds_remaining === "number"
        ? data.seconds_remaining
        : Number(data.days_remaining) * 86400;
    $("days").textContent =
      lastReading && lastReading.is_clogged ? "înfundat" : formatRemaining(secs);
    $("r2-badge").textContent = `R² ${fmt(data.r_squared, 3)}`;
    $("predict-note").textContent = `${data.points_used} puncte · fereastră ${PREDICT_HOURS} h`;
    return;
  }

  // Filter already fully clogged: pressure has hit its ceiling and plateaued,
  // so there is no rising trend left to fit - that is expected, not an error.
  if (lastReading && lastReading.is_clogged) {
    $("days").textContent = "înfundat";
    $("r2-badge").textContent = "—";
    $("predict-note").textContent = "filtru complet înfundat — presiune la maxim";
    return;
  }

  // No usable regression fit: too few points, or the trend is not rising
  // (typical right after the sensor restarted, when the window still spans an
  // old cycle). Fall back to the simulator's own estimate and say why.
  const NOTE = {
    insufficient_data: "date insuficiente — aștept ~5 citiri",
    stable:
      "trend neconcludent — senzorul a fost repornit recent sau rulează discontinuu",
  };
  const modelDays = lastReading && lastReading.days_remaining_model;
  const haveModel = typeof modelDays === "number";
  $("days").textContent = haveModel ? formatRemaining(modelDays * 86400) : "–";
  $("r2-badge").textContent = haveModel ? "model senzor" : "R² –";
  $("predict-note").textContent = NOTE[data.status] || data.message || "—";
}

async function pollLatest() {
  const data = await getJSON("/latest");
  if (data.status === "no_data") {
    lastReading = null;
    $("clog-note").textContent = "aștept date de la senzor…";
    return;
  }
  lastReading = data;
  const p = data.pressure_drop_bar;
  $("m-pressure").textContent = fmt(p, 3);
  $("m-flow").textContent = fmt(data.flow_rate_lmin, 1);
  $("m-turb").textContent = fmt(data.turbidity_ntu, 2);
  $("m-pressure-delta").textContent = deltaText(p, BASE.pressure);
  $("m-flow-delta").textContent = deltaText(data.flow_rate_lmin, BASE.flow);
  $("m-turb-delta").textContent = deltaText(data.turbidity_ntu, BASE.turbidity);

  updateGauge((p / clogThreshold) * 100);
  $("clog-note").textContent = data.is_clogged
    ? "filtru înfundat - necesită înlocuire"
    : `prag înfundare: ${clogThreshold} bar`;
}

async function pollHistory() {
  const data = await getJSON(`/history?hours=${historyHours}`);
  const all = (data.readings || [])
    .map((r) => r.pressure_drop_bar)
    .filter((v) => typeof v === "number");
  const pts = currentCycle(all);
  drawSpark(pts);
  const hidden = all.length - pts.length;
  $("spark-note").textContent =
    hidden > 0
      ? `${pts.length} citiri (${hidden} dintr-un ciclu anterior ascunse)`
      : `${pts.length} citiri`;
}

/* A filter cycle ends when the pressure collapses (filter replaced or sensor
 * restarted). Plot only the readings since the last such drop, so the current
 * cycle's gradual rise is not squashed flat by a previous cycle's peak. */
function currentCycle(values) {
  let start = 0;
  for (let i = 1; i < values.length; i++) {
    if (values[i - 1] - values[i] > 0.3) start = i;
  }
  return values.slice(start);
}

function drawSpark(values) {
  const svg = $("spark");
  svg.innerHTML = "";
  if (values.length < 2) {
    $("spark-note").textContent = "date insuficiente pentru grafic";
    return;
  }
  const W = 600;
  const H = 160;
  const pad = 6;
  const max = Math.max(...values, clogThreshold);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const x = (i) => pad + (i / (values.length - 1)) * (W - 2 * pad);
  const y = (v) => H - pad - ((v - min) / span) * (H - 2 * pad);

  const line = values
    .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  const area = `${line} L${x(values.length - 1).toFixed(1)},${H - pad} L${x(0).toFixed(1)},${H - pad} Z`;

  const ns = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs) => {
    const el = document.createElementNS(ns, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  };
  svg.appendChild(mk("path", { class: "area", d: area }));
  svg.appendChild(
    mk("path", { class: "line", d: line, "vector-effect": "non-scaling-stroke" }),
  );
  const ty = y(clogThreshold);
  if (ty >= 0 && ty <= H) {
    svg.appendChild(
      mk("line", {
        class: "threshold",
        x1: pad,
        y1: ty.toFixed(1),
        x2: W - pad,
        y2: ty.toFixed(1),
        "vector-effect": "non-scaling-stroke",
      }),
    );
  }
}

async function poll() {
  try {
    await pollPredict(); // resolves clogThreshold before the gauge uses it
    await pollLatest();
    if (tick % HISTORY_EVERY === 0) await pollHistory();
    setConn("ok", "conectat");
    $("updated").textContent =
      "actualizat " + new Date().toLocaleTimeString("ro-RO");
  } catch (err) {
    setConn("error", "eroare conexiune");
    console.error(err);
  } finally {
    tick++;
  }
}

$("range-buttons").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-h]");
  if (!btn) return;
  historyHours = parseFloat(btn.dataset.h);
  for (const b of $("range-buttons").children) {
    b.classList.toggle("active", b === btn);
  }
  pollHistory().catch((err) => console.error(err));
});

/* The Grafana address depends on where the stack runs (localhost:3000 with
 * docker compose, /grafana/ behind CloudFront on AWS) - the backend knows it. */
getJSON("/config")
  .then((cfg) => { $("grafana-link").href = cfg.grafana_url; })
  .catch((err) => console.error(err));

poll();
setInterval(poll, POLL_MS);
