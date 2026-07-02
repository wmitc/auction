"""English (ascending-clock) auction with information leakage.

The price rises from zero; bidders drop out irreversibly; the last one
standing wins at the price where the penultimate bidder left. Under common
values the dropout prices *leak information*: each early exit reveals (a
function of) the leaver's signal, and sophisticated bidders re-solve their
break-even price on the fly. This is the Milgrom-Weber (1982) "button
auction" — the mechanism where staying in is safe exactly up to

    E[V | my signal, every remaining rival tied with my signal, what the
         dropouts revealed]

(the *pivotal* estimate: the marginal case in which you win right now).
For our uniform noise structure that estimate is the midpoint of

    [max(v_low, s - a),  min(v_high, min(s, lowest revealed signal) + a)]

so only the *lowest* revealed signal matters, and with no dropouts yet the
rule collapses to the plain posterior mean — in an English auction the
mechanism itself corrects the winner's curse, which is exactly why it
raises more revenue than the sealed-bid format (the linkage principle).

Strategies:

* Tourist  — rides the clock to its signal, ignoring everything.
* Hedger   — a flat 10% shade of E[V | s], ignoring dropouts.
* Bayesian — the pivotal estimate, but never updates on dropouts.
* Shark    — full equilibrium: inverts each dropout price back to a signal
             (assuming the leaver was playing equilibrium) and re-solves.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .bayes import posterior_mean
from .bots import Bayesian, Hedger, Shark, Tourist
from .engine import AuctionConfig, draw_round


@dataclass(frozen=True)
class Dropout:
    price: float
    bidder: int
    inferred_signal: float  # equilibrium inversion of the dropout price


@dataclass(frozen=True)
class EnglishResult:
    true_value: float
    signals: tuple[float, ...]
    dropouts: tuple[Dropout, ...]  # in exit order, prices non-decreasing
    winner: int
    price: float
    pnl: tuple[float, ...]


def pivotal_estimate(signal: float, min_revealed: float, cfg: AuctionConfig) -> float:
    """E[V | s, remaining rivals tied at s, lowest revealed signal].

    ``min_revealed`` is +inf when nothing has been revealed yet, in which
    case this is the plain posterior mean.
    """
    lo = max(cfg.v_low, signal - cfg.noise)
    hi = min(cfg.v_high, min(signal, min_revealed) + cfg.noise)
    hi = max(hi, lo)  # inconsistent inference can't push the estimate below lo
    return (lo + hi) / 2


def invert_dropout(price: float, min_revealed: float, cfg: AuctionConfig) -> float:
    """The signal an equilibrium bidder must have held to leave at ``price``.

    Solves pivotal_estimate(s, min_revealed) = price by bisection (the
    estimate is monotone non-decreasing in s; on flat segments the lowest
    consistent signal is returned).
    """
    lo, hi = cfg.v_low - cfg.noise, cfg.v_high + cfg.noise
    if pivotal_estimate(lo, min_revealed, cfg) >= price:
        return lo
    if pivotal_estimate(hi, min_revealed, cfg) <= price:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if pivotal_estimate(mid, min_revealed, cfg) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bot_threshold(bot, signal: float, min_revealed: float, cfg: AuctionConfig) -> float:
    """The clock price at which this bot exits, given what has been revealed."""
    if isinstance(bot, Tourist):
        return max(cfg.v_low, min(signal, cfg.v_high))
    if isinstance(bot, Hedger):
        return (1 - bot.shade) * posterior_mean(signal, cfg)
    if isinstance(bot, Bayesian):
        return pivotal_estimate(signal, math.inf, cfg)
    if isinstance(bot, Shark):
        return pivotal_estimate(signal, min_revealed, cfg)
    raise TypeError(f"no English strategy for {type(bot).__name__}")


def run_english(
    cfg: AuctionConfig,
    bidders: list,
    rng: random.Random,
    *,
    true_value: float | None = None,
    signals: list[float] | None = None,
    player_index: int | None = None,
    player_drop: float | None = None,
) -> EnglishResult:
    """Simulate one clock auction.

    ``bidders`` may contain an external player at ``player_index``: that
    seat exits when the clock reaches ``player_drop`` (never, if None).
    Pass ``true_value``/``signals`` to replay a pre-drawn round.
    """
    n = len(bidders)
    if true_value is None or signals is None:
        true_value, signals = draw_round(cfg, n, rng)

    active = set(range(n))
    dropouts: list[Dropout] = []
    price = cfg.v_low
    min_revealed = math.inf

    def threshold(i: int) -> float:
        if i == player_index:
            return math.inf if player_drop is None else player_drop
        return bot_threshold(bidders[i], signals[i], min_revealed, cfg)

    while len(active) > 1:
        # nobody can leave below the current clock price
        levels = {i: max(threshold(i), price) for i in active}
        exit_price = min(levels.values())
        leavers = sorted(i for i, t in levels.items() if t == exit_price)
        price = exit_price

        if len(leavers) == len(active):
            # everyone left standing quits together: one random leaver wins
            winner = rng.choice(leavers)
            leavers.remove(winner)
            for i in leavers:
                dropouts.append(Dropout(price, i, invert_dropout(price, min_revealed, cfg)))
            active = {winner}
            break

        rng.shuffle(leavers)
        for i in leavers:
            inferred = invert_dropout(price, min_revealed, cfg)
            dropouts.append(Dropout(price, i, inferred))
            min_revealed = min(min_revealed, inferred)
            active.discard(i)

    winner = active.pop()
    pnl = [0.0] * n
    pnl[winner] = true_value - price
    return EnglishResult(
        true_value=true_value,
        signals=tuple(signals),
        dropouts=tuple(dropouts),
        winner=winner,
        price=price,
        pnl=tuple(pnl),
    )
