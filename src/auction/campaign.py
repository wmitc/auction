"""Campaign structure: level definitions, pass rules, and the score benchmark.

Each level is a fixed lineup of opponents and a number of rounds. The player
starts every level with a fresh bankroll; dropping to zero or below busts the
level, and finishing above the starting bankroll passes it. The leaderboard
metric is *excess PnL per round* over what a Shark would be expected to earn
in the player's seat — raw PnL is too lucky to brag about.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .bots import Bayesian, Hedger, Shark, Tourist
from .engine import AuctionConfig, run_round

STARTING_BANKROLL = 100.0


@dataclass(frozen=True)
class Level:
    number: int
    name: str
    tagline: str
    opponents: tuple
    rounds: int


LEVELS: tuple[Level, ...] = (
    Level(1, "First Blood", "One naive rival. How hard can it be?", (Tourist(),), 10),
    Level(2, "Crowded Room", "More bidders, more optimistic winners.",
          (Tourist(), Tourist(), Tourist()), 10),
    Level(3, "Mixed Company", "Someone here has learned to shade.",
          (Tourist(), Tourist(), Hedger()), 12),
    Level(4, "Hedged", "Flat discounts everywhere. Still exploitable.",
          (Hedger(), Hedger(), Hedger()), 12),
    Level(5, "Card Counters", "Half the table knows the conditional expectation.",
          (Hedger(), Hedger(), Bayesian(), Bayesian()), 15),
    Level(6, "Zero Margin", "Perfectly calibrated rivals. Where is your edge?",
          (Bayesian(), Bayesian(), Bayesian()), 15),
    Level(7, "Blood in the Water", "The equilibrium bidders have arrived.",
          (Bayesian(), Bayesian(), Shark(), Shark()), 15),
    Level(8, "Shark Tank", "Four equilibrium bidders. Respect the rent.",
          (Shark(), Shark(), Shark(), Shark()), 20),
    Level(9, "Feeding Frenzy", "Eight sharks. Shade like you mean it.",
          tuple(Shark() for _ in range(8)), 20),
)


def shark_benchmark(
    level: Level, cfg: AuctionConfig, seed: int = 0, n_rounds: int = 20_000
) -> float:
    """Expected PnL per round of a Shark sitting in the player's seat."""
    rng = random.Random(seed)
    bidders = [Shark(), *level.opponents]
    total = 0.0
    for _ in range(n_rounds):
        total += run_round(cfg, bidders, rng).pnl[0]
    return total / n_rounds


def level_status(bankroll: float, rounds_played: int, level: Level) -> str:
    """'busted', 'passed', 'failed' (survived but no profit), or 'playing'."""
    if bankroll <= 0:
        return "busted"
    if rounds_played >= level.rounds:
        return "passed" if bankroll > STARTING_BANKROLL else "failed"
    return "playing"
