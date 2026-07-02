"""Sealed-bid first-price common-value auction engine.

An item has an unknown common value V ~ Uniform(v_low, v_high). Each bidder
observes a private signal s_i = V + eps_i with eps_i ~ Uniform(-noise, noise).
The highest bid wins, the winner pays their bid and books PnL = V - bid.
Everything is driven by an injected ``random.Random`` so rounds are
reproducible given a seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class AuctionConfig:
    v_low: float = 0.0
    v_high: float = 100.0
    noise: float = 10.0  # half-width a of the Uniform(-a, a) signal noise

    def __post_init__(self) -> None:
        if self.v_high <= self.v_low:
            raise ValueError("v_high must exceed v_low")
        if self.noise <= 0:
            raise ValueError("noise must be positive")
        if 2 * self.noise >= self.v_high - self.v_low:
            raise ValueError("noise band must be narrower than the value range")


@dataclass(frozen=True)
class RoundResult:
    true_value: float
    signals: tuple[float, ...]
    bids: tuple[float, ...]
    winner: int
    price: float
    pnl: tuple[float, ...]


def draw_round(cfg: AuctionConfig, n_bidders: int, rng: random.Random) -> tuple[float, list[float]]:
    """Draw the true value and one noisy signal per bidder."""
    if n_bidders < 1:
        raise ValueError("need at least one bidder")
    v = rng.uniform(cfg.v_low, cfg.v_high)
    signals = [v + rng.uniform(-cfg.noise, cfg.noise) for _ in range(n_bidders)]
    return v, signals


def settle(
    true_value: float, signals: list[float], bids: list[float], rng: random.Random
) -> RoundResult:
    """Resolve a sealed-bid first-price auction; ties broken uniformly at random."""
    if len(bids) != len(signals) or not bids:
        raise ValueError("bids and signals must be equal-length, non-empty")
    best = max(bids)
    contenders = [i for i, b in enumerate(bids) if b == best]
    winner = contenders[0] if len(contenders) == 1 else rng.choice(contenders)
    pnl = [0.0] * len(bids)
    pnl[winner] = true_value - best
    return RoundResult(
        true_value=true_value,
        signals=tuple(signals),
        bids=tuple(bids),
        winner=winner,
        price=best,
        pnl=tuple(pnl),
    )


def run_round(cfg: AuctionConfig, bidders: list, rng: random.Random) -> RoundResult:
    """Draw a round, collect one bid per bidder, and settle it.

    Each bidder must expose ``bid(signal, n_bidders, cfg) -> float``.
    """
    v, signals = draw_round(cfg, len(bidders), rng)
    n = len(bidders)
    bids = [bot.bid(s, n, cfg) for bot, s in zip(bidders, signals, strict=True)]
    return settle(v, signals, bids, rng)
