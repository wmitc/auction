"""Web backend for the winner's-curse game.

Sessions live in memory; each holds a campaign position, a bankroll, the
in-flight round (true value and all signals are drawn at round start, but
only the player's signal is revealed until they bid), and the running
autopsy statistics. Run with:

    uvicorn web.app:app --reload
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auction import AuctionConfig, Shark, equilibrium_bid, max_signal_posterior_mean
from auction.bots import Bayesian, Hedger, Tourist
from auction.campaign import LEVELS, STARTING_BANKROLL, Level, level_status, shark_benchmark
from auction.engine import draw_round, settle
from auction.english import pivotal_estimate, run_english

CFG = AuctionConfig()
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Winner's Curse")


class BidRequest(BaseModel):
    bid: float


@dataclass
class Session:
    rng: random.Random
    level_index: int = 0
    bankroll: float = STARTING_BANKROLL
    rounds_played: int = 0
    status: str = "playing"  # playing | awaiting_bid | passed | failed | busted | complete
    pending: dict[str, Any] | None = None  # {true_value, signals} for the in-flight round
    gaps: list[float] = field(default_factory=list)  # bid - optimal bid, whole campaign
    level_pnl: float = 0.0
    beaten: list[int] = field(default_factory=list)
    scores: dict[int, float] = field(default_factory=dict)  # level -> excess PnL/round
    last_autopsy: dict[str, Any] | None = None

    @property
    def level(self) -> Level:
        return LEVELS[self.level_index]


SESSIONS: dict[str, Session] = {}
BENCHMARKS: dict[int, float] = {}


def benchmark(level: Level) -> float:
    if level.number not in BENCHMARKS:
        BENCHMARKS[level.number] = shark_benchmark(level, CFG, seed=level.number)
    return BENCHMARKS[level.number]


def get_session(session_id: str) -> Session:
    s = SESSIONS.get(session_id)
    if s is None:
        raise HTTPException(404, "unknown session")
    return s


def state_payload(s: Session) -> dict[str, Any]:
    lvl = s.level
    return {
        "level": {
            "number": lvl.number,
            "name": lvl.name,
            "tagline": lvl.tagline,
            "rounds": lvl.rounds,
            "opponents": [b.name for b in lvl.opponents],
            "n_bidders": len(lvl.opponents) + 1,
        },
        "total_levels": len(LEVELS),
        "bankroll": round(s.bankroll, 2),
        "starting_bankroll": STARTING_BANKROLL,
        "rounds_played": s.rounds_played,
        "status": s.status,
        "gaps": [round(g, 2) for g in s.gaps],
        "beaten": s.beaten,
        "scores": {str(k): round(v, 3) for k, v in s.scores.items()},
        "benchmark": round(benchmark(lvl), 3),
        "noise": CFG.noise,
        "value_range": [CFG.v_low, CFG.v_high],
        "last_autopsy": s.last_autopsy,
    }


@app.post("/api/session")
def create_session(seed: int | None = None) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = Session(rng=random.Random(seed))
    return {"session_id": session_id, **state_payload(SESSIONS[session_id])}


@app.get("/api/session/{session_id}")
def get_state(session_id: str) -> dict[str, Any]:
    return state_payload(get_session(session_id))


@app.post("/api/session/{session_id}/round")
def start_round(session_id: str) -> dict[str, Any]:
    s = get_session(session_id)
    if s.status not in ("playing",):
        raise HTTPException(409, f"cannot start a round while status is '{s.status}'")
    n = len(s.level.opponents) + 1
    true_value, signals = draw_round(CFG, n, s.rng)
    s.pending = {"true_value": true_value, "signals": signals}
    s.status = "awaiting_bid"
    return {
        "round_number": s.rounds_played + 1,
        "your_signal": round(signals[0], 2),
        "n_bidders": n,
        **state_payload(s),
    }


@app.post("/api/session/{session_id}/bid")
def submit_bid(session_id: str, req: BidRequest) -> dict[str, Any]:
    s = get_session(session_id)
    if s.status != "awaiting_bid" or s.pending is None:
        raise HTTPException(409, "no round awaiting a bid")
    if not (CFG.v_low - CFG.noise <= req.bid <= CFG.v_high + CFG.noise):
        raise HTTPException(422, "bid outside the plausible range")

    true_value: float = s.pending["true_value"]
    signals: list[float] = s.pending["signals"]
    n = len(signals)
    opponents = s.level.opponents
    bids = [req.bid] + [b.bid(sig, n, CFG) for b, sig in zip(opponents, signals[1:], strict=True)]
    result = settle(true_value, signals, bids, s.rng)

    your_signal = signals[0]
    optimal = equilibrium_bid(your_signal, n, CFG)
    estimate = max_signal_posterior_mean(your_signal, n, CFG)
    gap = req.bid - optimal
    s.gaps.append(gap)
    s.bankroll += result.pnl[0]
    s.level_pnl += result.pnl[0]
    s.rounds_played += 1
    s.pending = None
    s.status = level_status(s.bankroll, s.rounds_played, s.level)

    entries = [
        {
            "name": "You" if i == 0 else f"{opponents[i - 1].name} {i}",
            "signal": round(result.signals[i], 2),
            "bid": round(result.bids[i], 2),
            "pnl": round(result.pnl[i], 2),
            "is_you": i == 0,
            "is_winner": i == result.winner,
        }
        for i in range(n)
    ]
    autopsy = {
        "round_number": s.rounds_played,
        "true_value": round(true_value, 2),
        "entries": sorted(entries, key=lambda e: -e["bid"]),
        "your_pnl": round(result.pnl[0], 2),
        "you_won": result.winner == 0,
        "optimal_bid": round(optimal, 2),
        "curse_corrected_estimate": round(estimate, 2),
        "shading_gap": round(gap, 2),
        "cumulative_gap": round(sum(s.gaps), 2),
    }
    s.last_autopsy = autopsy

    extra: dict[str, Any] = {}
    if s.status == "passed":
        score = s.level_pnl / s.level.rounds - benchmark(s.level)
        s.scores[s.level.number] = score
        if s.level.number not in s.beaten:
            s.beaten.append(s.level.number)
        extra["level_score"] = round(score, 3)
        extra["bot_strategies"] = sorted(
            {b.name: b.describe() for b in s.level.opponents}.items()
        )
    return {"autopsy": autopsy, **extra, **state_payload(s)}


@app.post("/api/session/{session_id}/advance")
def advance_level(session_id: str) -> dict[str, Any]:
    s = get_session(session_id)
    if s.status != "passed":
        raise HTTPException(409, "level not passed")
    if s.level_index + 1 >= len(LEVELS):
        s.status = "complete"
        return state_payload(s)
    s.level_index += 1
    _reset_level(s)
    return state_payload(s)


@app.post("/api/session/{session_id}/restart")
def restart_level(session_id: str) -> dict[str, Any]:
    s = get_session(session_id)
    if s.status not in ("busted", "failed", "awaiting_bid", "playing"):
        raise HTTPException(409, f"cannot restart while status is '{s.status}'")
    _reset_level(s)
    return state_payload(s)


def _reset_level(s: Session) -> None:
    s.bankroll = STARTING_BANKROLL
    s.rounds_played = 0
    s.level_pnl = 0.0
    s.pending = None
    s.status = "playing"
    s.last_autopsy = None


# ---------------------------------------------------------------------------
# English (ascending clock) arena
# ---------------------------------------------------------------------------

ARENA_LINEUP = (Tourist(), Hedger(), Bayesian(), Shark(), Shark())


class DropRequest(BaseModel):
    price: float | None = None  # None = stayed until every bot left


@dataclass
class ArenaSession:
    rng: random.Random
    bankroll: float = STARTING_BANKROLL
    rounds_played: int = 0
    total_pnl: float = 0.0
    pending: dict[str, Any] | None = None
    status: str = "playing"  # playing | awaiting_drop


ARENAS: dict[str, ArenaSession] = {}
_ARENA_BENCHMARK: float | None = None


def arena_benchmark(n_rounds: int = 3_000) -> float:
    global _ARENA_BENCHMARK
    if _ARENA_BENCHMARK is None:
        rng = random.Random(0)
        bidders = [Shark(), *ARENA_LINEUP]
        total = sum(run_english(CFG, bidders, rng).pnl[0] for _ in range(n_rounds))
        _ARENA_BENCHMARK = total / n_rounds
    return _ARENA_BENCHMARK


def arena_name(i: int) -> str:
    return "You" if i == 0 else f"{ARENA_LINEUP[i - 1].name} {i}"


def get_arena(session_id: str) -> ArenaSession:
    s = ARENAS.get(session_id)
    if s is None:
        raise HTTPException(404, "unknown arena session")
    return s


def arena_state(s: ArenaSession) -> dict[str, Any]:
    return {
        "bankroll": round(s.bankroll, 2),
        "rounds_played": s.rounds_played,
        "status": s.status,
        "pnl_per_round": round(s.total_pnl / s.rounds_played, 3) if s.rounds_played else 0.0,
        "benchmark": round(arena_benchmark(), 3),
        "opponents": [b.name for b in ARENA_LINEUP],
        "noise": CFG.noise,
        "value_range": [CFG.v_low, CFG.v_high],
    }


@app.post("/api/english/session")
def create_arena(seed: int | None = None) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    ARENAS[session_id] = ArenaSession(rng=random.Random(seed))
    return {"session_id": session_id, **arena_state(ARENAS[session_id])}


@app.post("/api/english/{session_id}/round")
def arena_round(session_id: str) -> dict[str, Any]:
    s = get_arena(session_id)
    if s.status != "playing":
        raise HTTPException(409, f"cannot start a round while status is '{s.status}'")
    n = len(ARENA_LINEUP) + 1
    true_value, signals = draw_round(CFG, n, s.rng)
    # timeline of bot exits assuming the player never drops; bots only react
    # to dropout *events*, so this is exactly what the player watches live
    schedule = run_english(
        CFG, ["player", *ARENA_LINEUP], random.Random(s.rng.random()),
        true_value=true_value, signals=signals, player_index=0, player_drop=None,
    )
    events = []
    min_revealed = float("inf")
    for d in schedule.dropouts:
        min_revealed = min(min_revealed, d.inferred_signal)
        events.append(
            {
                "price": round(d.price, 2),
                "name": arena_name(d.bidder),
                "inferred_signal": round(d.inferred_signal, 2),
                "your_hint_after": round(pivotal_estimate(signals[0], min_revealed, CFG), 2),
            }
        )
    s.pending = {"true_value": true_value, "signals": signals}
    s.status = "awaiting_drop"
    return {
        "round_number": s.rounds_played + 1,
        "your_signal": round(signals[0], 2),
        "your_hint_start": round(pivotal_estimate(signals[0], float("inf"), CFG), 2),
        "n_bidders": n,
        "events": events,
        "win_price": round(schedule.price, 2),
        **arena_state(s),
    }


@app.post("/api/english/{session_id}/drop")
def arena_drop(session_id: str, req: DropRequest) -> dict[str, Any]:
    s = get_arena(session_id)
    if s.status != "awaiting_drop" or s.pending is None:
        raise HTTPException(409, "no clock running")
    true_value: float = s.pending["true_value"]
    signals: list[float] = s.pending["signals"]

    result = run_english(
        CFG, ["player", *ARENA_LINEUP], s.rng,
        true_value=true_value, signals=signals,
        player_index=0, player_drop=req.price,
    )
    # counterfactual: a Shark holding your signal, same round
    shadow = run_english(
        CFG, [Shark(), *ARENA_LINEUP], random.Random(1),
        true_value=true_value, signals=signals,
    )

    s.bankroll += result.pnl[0]
    s.total_pnl += result.pnl[0]
    s.rounds_played += 1
    s.pending = None
    s.status = "playing"

    timeline = [
        {
            "name": arena_name(d.bidder),
            "price": round(d.price, 2),
            "inferred_signal": round(d.inferred_signal, 2),
            "actual_signal": round(result.signals[d.bidder], 2),
            "is_you": d.bidder == 0,
        }
        for d in result.dropouts
    ]
    autopsy = {
        "round_number": s.rounds_played,
        "true_value": round(true_value, 2),
        "timeline": timeline,
        "winner": arena_name(result.winner),
        "you_won": result.winner == 0,
        "price": round(result.price, 2),
        "your_pnl": round(result.pnl[0], 2),
        "shadow_shark": {
            "won": shadow.winner == 0,
            "price": round(shadow.price, 2),
            "pnl": round(shadow.pnl[0], 2),
        },
    }
    return {"autopsy": autopsy, **arena_state(s)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/english")
def english_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "english.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
