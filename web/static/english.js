/* English (ascending clock) arena. The server precomputes the bot dropout
   timeline assuming the player stays in; the client animates the clock,
   replays events as the price passes them, and reports the price at which
   the player pressed Drop (or null if they outlasted everyone). */

const $ = (id) => document.getElementById(id);
const SPEED = 9; // price units per second

let sessionId = null;
let state = null;
let round = null;
let lastBankroll = null;
let clock = { raf: null, price: 0, nextEvent: 0, t0: 0, p0: 0 };

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
}

const fmt = (x, signed = false) => {
  const s = Number(x).toFixed(2);
  return signed && x > 0 ? `+${s}` : s;
};

function show(id) {
  ["start-panel", "clock-panel", "autopsy-panel"].forEach((p) =>
    $(p).classList.toggle("hidden", p !== id));
}

function renderHeader() {
  const b = state.bankroll;
  $("bankroll").textContent = fmt(b);
  const delta = lastBankroll === null ? 0 : b - lastBankroll;
  const el = $("bankroll-delta");
  el.textContent = delta === 0 ? "" : fmt(delta, true);
  el.className = "tile-delta " + (delta > 0 ? "pos" : delta < 0 ? "neg" : "");
  lastBankroll = b;
  $("rounds").textContent = state.rounds_played;
  $("ppr").textContent = fmt(state.pnl_per_round);
  $("score-line").textContent =
    `Shark benchmark in your seat: ${fmt(state.benchmark, true)}/round — ` +
    `your edge: ${fmt(state.pnl_per_round - state.benchmark, true)}`;
}

function renderStart() {
  $("start-text").innerHTML =
    `Six bidders: you, plus <b>${state.opponents.join(", ")}</b>. The clock climbs from 0; ` +
    `drop out or win at the price where the last rival leaves. Watch the exits — every ` +
    `dropout reveals a signal, and your break-even estimate updates with it.`;
  show("start-panel");
}

function setHint(value) {
  $("hint").innerHTML = `Break-even if you won <i>right now</i>: <b>${fmt(value)}</b>` +
    ` — staying past it is bidding above the pivotal estimate.`;
}

function addFeedLine(ev) {
  const li = document.createElement("li");
  li.innerHTML = `<b>${ev.name}</b> dropped at <b>${fmt(ev.price)}</b> — ` +
    `implies their signal ≈ ${fmt(ev.inferred_signal)}. Your break-even is now ` +
    `<b>${fmt(ev.your_hint_after)}</b>.`;
  $("feed").prepend(li);
}

function startClock() {
  clock = { raf: null, price: 0, nextEvent: 0, t0: performance.now(), p0: 0 };
  $("feed").innerHTML = "";
  $("signal").textContent = fmt(round.your_signal);
  setHint(round.your_hint_start);
  show("clock-panel");
  tick();
}

function tick() {
  const now = performance.now();
  let target = clock.p0 + ((now - clock.t0) / 1000) * SPEED;

  while (clock.nextEvent < round.events.length &&
         round.events[clock.nextEvent].price <= target) {
    const ev = round.events[clock.nextEvent++];
    addFeedLine(ev);
    setHint(ev.your_hint_after);
    // pause perception: restart the ramp at the event price
    clock.p0 = ev.price;
    clock.t0 = now;
    target = ev.price;
  }

  clock.price = target;
  $("price").textContent = clock.price.toFixed(1);

  if (clock.price >= round.win_price) {
    stopClock();
    resolve(null); // outlasted every bot
    return;
  }
  clock.raf = requestAnimationFrame(tick);
}

function stopClock() {
  if (clock.raf) cancelAnimationFrame(clock.raf);
  clock.raf = null;
}

async function resolve(price) {
  const resp = await api(`/api/english/${sessionId}/drop`, { price });
  state = resp;
  renderHeader();
  renderAutopsy(resp.autopsy);
}

function renderAutopsy(a) {
  $("true-value").textContent = fmt(a.true_value);
  const pnlEl = $("round-pnl");
  pnlEl.textContent = fmt(a.your_pnl, true);
  pnlEl.className = "hero " + (a.your_pnl > 0 ? "pos" : a.your_pnl < 0 ? "neg" : "");

  const rows = a.timeline.map((e) =>
    `<tr class="${e.is_you ? "you" : ""}"><td class="medal"></td><td>${e.name}</td>
     <td class="num">${fmt(e.price)}</td><td class="num">${fmt(e.inferred_signal)}</td>
     <td class="num">${fmt(e.actual_signal)}</td></tr>`);
  rows.push(
    `<tr class="${a.you_won ? "you" : ""}"><td class="medal">🏆</td><td>${a.winner} (won)</td>
     <td class="num">${fmt(a.price)}</td><td class="num">—</td><td class="num">—</td></tr>`);
  $("timeline-rows").innerHTML = rows.join("");

  const sh = a.shadow_shark;
  let msg = `A Shark holding your signal would have ` +
    (sh.won ? `<b>won at ${fmt(sh.price)}</b> for a PnL of <b>${fmt(sh.pnl, true)}</b>.`
            : `dropped out and booked <b>0.00</b>.`);
  if (a.you_won && a.your_pnl < 0) {
    msg += ` You outlasted everyone — which means everyone else thought it was worth less.`;
  }
  msg += ` Compare the inferred signals with the actual ones: inference is exact for ` +
    `equilibrium bidders and biased for the naive ones.`;
  $("coach").innerHTML = msg;
  show("autopsy-panel");
}

async function startRound() {
  round = await api(`/api/english/${sessionId}/round`);
  state = round;
  renderHeader();
  startClock();
}

async function boot() {
  const resp = await api("/api/english/session");
  sessionId = resp.session_id;
  state = resp;
  renderHeader();
  renderStart();
  if (location.hash === "#demo") {
    await startRound();
    setTimeout(() => { if (clock.raf) { stopClock(); resolve(clock.price); } }, 2500);
  }
}

$("start-btn").onclick = startRound;
$("next-btn").onclick = startRound;
$("drop-btn").onclick = () => { stopClock(); resolve(clock.price); };
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && clock.raf) { e.preventDefault(); stopClock(); resolve(clock.price); }
});

boot();
