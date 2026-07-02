"""Bidder strategies, from naive to equilibrium.

Every bot exposes ``bid(signal, n_bidders, cfg) -> float`` plus a name and a
human-readable strategy description (surfaced in the game's bot-inspection
screen after a level is beaten).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .bayes import equilibrium_bid, max_signal_posterior_mean, posterior_mean
from .engine import AuctionConfig


@dataclass(frozen=True)
class Tourist:
    """Bids the signal itself — the naive strategy the game exists to cure."""

    name: str = "Tourist"

    def bid(self, signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
        return max(cfg.v_low, min(signal, cfg.v_high))

    def describe(self) -> str:
        return (
            "Bids its signal. Feels safe — the signal is an unbiased estimate of V — "
            "but conditional on winning, the signal was likely the most optimistic "
            "of the lot, so the Tourist systematically overpays."
        )


@dataclass(frozen=True)
class Hedger:
    """Shades the posterior mean by a fixed fraction, regardless of competition."""

    shade: float = 0.10
    name: str = field(default="Hedger")

    def bid(self, signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
        return (1 - self.shade) * posterior_mean(signal, cfg)

    def describe(self) -> str:
        return (
            f"Bids E[V | signal] shaded by a flat {self.shade:.0%}. Better than nothing, "
            "but the correct shade depends on how many rivals you beat — a fixed haircut "
            "is too timid in small fields and too brave in big ones."
        )


@dataclass(frozen=True)
class Bayesian:
    """Corrects the winner's curse but keeps zero margin."""

    name: str = "Bayesian"

    def bid(self, signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
        return max_signal_posterior_mean(signal, n_bidders, cfg)

    def describe(self) -> str:
        return (
            "Bids E[V | signal, signal is the highest of N] — exactly what the item is "
            "worth given that you won. Immune to the curse, but bids away its whole "
            "edge: expected PnL is zero against copies of itself."
        )


@dataclass(frozen=True)
class Shark:
    """Plays the symmetric risk-neutral Nash equilibrium."""

    name: str = "Shark"

    def bid(self, signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
        return equilibrium_bid(signal, n_bidders, cfg)

    def describe(self) -> str:
        return (
            "Plays the symmetric equilibrium: roughly signal - a (bid as if your noise "
            "draw were maximally optimistic), keeping an information rent of about "
            "2a/(N+1) per win. No unilateral deviation improves its expected PnL."
        )


ALL_BOTS = (Tourist, Hedger, Bayesian, Shark)
