/* Winner's Curse — SPA driving the FastAPI backend. */

const $ = (id) => document.getElementById(id);
const panels = ["deal-panel", "bid-panel", "autopsy-panel", "strategies-panel", "complete-panel"];

let sessionId = null;
let state = null;
let lastBankroll = null;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || "POST",
    headers: { "Content-Type": "application/json" },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}

function show(...ids) {
  panels.forEach((p) => $(p).classList.toggle("hidden", !ids.includes(p)));
}

function fmt(x, signed = false) {
  const s = Number(x).toFixed(2);
  return signed && x > 0 ? `+${s}` : s;
}

function renderHeader() {
  const lvl = state.level;
  $("level-kicker").textContent = `Level ${lvl.number} of ${state.total_levels}`;
  $("level-name").textContent = lvl.name;
  $("level-tagline").textContent = lvl.tagline;
  $("n-bidders").textContent = lvl.n_bidders;
  $("round-counter").textContent = `${state.rounds_played} / ${lvl.rounds}`;

  const b = state.bankroll;
  $("bankroll").textContent = fmt(b);
  const delta = lastBankroll === null ? 0 : b - lastBankroll;
  const el = $("bankroll-delta");
  el.textContent = delta === 0 ? "" : fmt(delta, true);
  el.className = "tile-delta " + (delta > 0 ? "pos" : delta < 0 ? "neg" : "");
  lastBankroll = b;

  const scores = Object.entries(state.scores);
  $("score-line").textContent = scores.length
    ? "Luck-adjusted scores (PnL/round − Shark benchmark): " +
      scores.map(([k, v]) => `L${k}: ${v >= 0 ? "+" : ""}${v.toFixed(2)}`).join("  ·  ")
    : "Score = your PnL per round minus a Shark's expected PnL in your seat.";
}

function renderDeal() {
  const lvl = state.level;
  const opps = {};
  lvl.opponents.forEach((n) => (opps[n] = (opps[n] || 0) + 1));
  const lineup = Object.entries(opps).map(([n, c]) => (c > 1 ? `${c}× ${n}` : n)).join(", ");
  $("deal-text").innerHTML =
    `You face <b>${lineup}</b>. The item is worth <b>V ~ Uniform(${state.value_range[0]}, ` +
    `${state.value_range[1]})</b> and every bidder sees V plus noise within ±${state.noise}. ` +
    `Survive ${lvl.rounds} rounds and finish above ${fmt(state.starting_bankroll)} to advance.`;
  show("deal-panel");
}

function renderBid(round) {
  $("signal-value").textContent = fmt(round.your_signal);
  $("signal-hint").textContent =
    `True value is within ±${state.noise} of this. ${round.n_bidders - 1} rivals hold their own signals.`;
  const start = Math.min(Math.max(round.your_signal, 0), 100);
  $("bid-slider").value = start;
  $("bid-input").value = start.toFixed(1);
  show("bid-panel");
  $("bid-input").focus();
}

function coachText(a) {
  const gap = a.shading_gap;
  let msg = `Equilibrium bid for your signal: <b>${fmt(a.optimal_bid)}</b> ` +
    `(the item is worth ${fmt(a.curse_corrected_estimate)} <i>given that you win</i>). ` +
    `You bid ${gap >= 0 ? "<b>" + fmt(gap) + " above</b>" : "<b>" + fmt(-gap) + " below</b>"} that.`;
  if (a.you_won && a.your_pnl < 0) {
    msg += ` You won <i>because</i> your signal was likely the most optimistic in the room — that's the winner's curse.`;
  } else if (a.you_won && a.your_pnl >= 0) {
    msg += ` A paid-for win — you kept your margin.`;
  } else if (gap < -3) {
    msg += ` Losing rounds is fine; most rounds aren't yours to win.`;
  }
  msg += ` Cumulative shading gap: <b>${fmt(a.cumulative_gap, true)}</b>.`;
  return msg;
}

function renderAutopsy(resp) {
  const a = resp.autopsy;
  $("true-value").textContent = fmt(a.true_value);
  const pnlEl = $("round-pnl");
  pnlEl.textContent = fmt(a.your_pnl, true);
  pnlEl.className = "hero " + (a.your_pnl > 0 ? "pos" : a.your_pnl < 0 ? "neg" : "");

  $("autopsy-rows").innerHTML = a.entries
    .map((e) => {
      const pnl = e.is_winner ? `<span class="${e.pnl >= 0 ? "pos" : "neg"}">${fmt(e.pnl, true)}</span>` : "—";
      return `<tr class="${e.is_you ? "you" : ""}">
        <td class="medal">${e.is_winner ? "🏆" : ""}</td>
        <td>${e.name}</td>
        <td class="num">${fmt(e.signal)}</td>
        <td class="num">${fmt(e.bid)}</td>
        <td class="num">${pnl}</td></tr>`;
    })
    .join("");

  $("coach").innerHTML = coachText(a);
  drawHistogram(state.gaps);

  const cta = $("autopsy-cta");
  cta.innerHTML = "";
  const btn = (label, cls, fn) => {
    const b = document.createElement("button");
    b.className = cls;
    b.textContent = label;
    b.onclick = fn;
    cta.appendChild(b);
  };
  if (state.status === "playing") {
    btn("Next round", "primary", deal);
  } else if (state.status === "passed") {
    const last = state.level.number === state.total_levels;
    btn(
      `Level passed — score ${fmt(resp.level_score, true)}` +
        (last ? " · finish campaign" : ` · onward to level ${state.level.number + 1}`),
      "primary",
      advance
    );
    renderStrategies(resp.bot_strategies || []);
  } else if (state.status === "failed") {
    btn(`Survived, but no profit (${fmt(state.bankroll - state.starting_bankroll, true)}) — retry level`, "ghost", restart);
  } else if (state.status === "busted") {
    btn("Busted. The curse collects — retry level", "ghost", restart);
  }
  show("autopsy-panel", ...(state.status === "passed" ? ["strategies-panel"] : []));
}

function renderStrategies(strategies) {
  $("strategies").innerHTML = strategies
    .map(([name, desc]) => `<div class="strategy"><div class="name">${name}</div><div class="desc">${desc}</div></div>`)
    .join("");
}

function renderComplete() {
  $("score-rows").innerHTML = Object.entries(state.scores)
    .map(([k, v]) => `<tr><td>Level ${k}</td><td class="num ${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${v.toFixed(3)}</td></tr>`)
    .join("");
  show("complete-panel");
}

function drawHistogram(gaps) {
  const c = $("histogram");
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height, pad = 6;
  ctx.clearRect(0, 0, W, H);
  const lo = -12, hi = 12, nbins = 24;
  const bins = new Array(nbins).fill(0);
  gaps.forEach((g) => {
    const x = Math.min(Math.max(g, lo + 1e-9), hi - 1e-9);
    bins[Math.floor(((x - lo) / (hi - lo)) * nbins)]++;
  });
  const maxBin = Math.max(1, ...bins);
  const bw = (W - 2 * pad) / nbins;
  bins.forEach((n, i) => {
    const h = (n / maxBin) * (H - 24);
    ctx.fillStyle = "#2a78d6";
    ctx.fillRect(pad + i * bw + 1, H - 16 - h, bw - 2, h);
  });
  // zero marker
  const x0 = pad + ((0 - lo) / (hi - lo)) * (W - 2 * pad);
  ctx.strokeStyle = "#0b0b0b";
  ctx.beginPath(); ctx.moveTo(x0, 4); ctx.lineTo(x0, H - 14); ctx.stroke();
  ctx.fillStyle = "#898781";
  ctx.font = "11px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("0", x0, H - 2);
  ctx.fillText(String(lo), pad + 8, H - 2);
  ctx.fillText("+" + hi, W - pad - 12, H - 2);
}

async function boot() {
  const resp = await api("/api/session");
  sessionId = resp.session_id;
  state = resp;
  renderHeader();
  renderDeal();
  if (location.hash === "#demo") {
    // dev/screenshot hook: play one naive round straight to the autopsy
    await deal();
    await submitBid();
  }
}

async function deal() {
  const resp = await api(`/api/session/${sessionId}/round`);
  state = resp;
  renderHeader();
  renderBid(resp);
}

async function submitBid() {
  const bid = parseFloat($("bid-input").value);
  if (Number.isNaN(bid)) return;
  const resp = await api(`/api/session/${sessionId}/bid`, { body: { bid } });
  state = resp;
  renderHeader();
  renderAutopsy(resp);
}

async function advance() {
  state = await api(`/api/session/${sessionId}/advance`);
  renderHeader();
  if (state.status === "complete") renderComplete();
  else renderDeal();
}

async function restart() {
  state = await api(`/api/session/${sessionId}/restart`);
  lastBankroll = null;
  renderHeader();
  renderDeal();
}

$("deal-btn").onclick = deal;
$("bid-btn").onclick = submitBid;
$("bid-slider").oninput = () => ($("bid-input").value = Number($("bid-slider").value).toFixed(1));
$("bid-input").oninput = () => ($("bid-slider").value = $("bid-input").value);
$("bid-input").onkeydown = (e) => { if (e.key === "Enter") submitBid(); };

boot();
