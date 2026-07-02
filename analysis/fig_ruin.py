"""Bankroll consequences: the curse is not an abstraction, it's ruin.

Every hero starts with 100 and plays rounds against four Sharks; a bankroll
at or below zero is absorbed. Left: sample Tourist and Shark trajectories.
Right: survival probability over time for all four strategies.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from fig_pnl import hero_bids
from style import BOT_COLORS, INK_2, MUTED, apply_style, save

from auction import AuctionConfig
from auction.vectorized import draw_rounds, equilibrium_bid

N = 5
PATHS = 4_000
T = 400
START = 100.0


def bankroll_paths(name: str, cfg: AuctionConfig, rng: np.random.Generator) -> np.ndarray:
    v, signals = draw_rounds(cfg, N, PATHS * T, rng)
    rival_best = equilibrium_bid(signals[:, 1:], N, cfg).max(axis=1)
    mine = hero_bids(name, signals[:, 0], cfg)
    pnl = np.where(mine > rival_best, v - mine, 0.0).reshape(PATHS, T)
    wealth = START + np.cumsum(pnl, axis=1)
    # absorb at ruin: freeze the path once it touches zero
    ruined = np.minimum.accumulate(wealth, axis=1) <= 0
    wealth = np.where(ruined, 0.0, wealth)
    return np.hstack([np.full((PATHS, 1), START), wealth])


def main() -> None:
    apply_style()
    cfg = AuctionConfig()
    rng = np.random.default_rng(11)
    paths = {name: bankroll_paths(name, cfg, rng) for name in BOT_COLORS}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.4, 4.0))
    t = np.arange(T + 1)
    for name in ("Tourist", "Shark"):
        color = BOT_COLORS[name]
        for row in paths[name][:22]:
            ax1.plot(t, row, color=color, lw=0.7, alpha=0.28, zorder=2)
        ax1.plot(t, np.median(paths[name], axis=0), color=color, lw=2.2, zorder=3)
    ax1.axhline(0, color=MUTED, lw=1)
    ax1.set_xlabel("rounds played")
    ax1.set_ylabel("bankroll")
    ax1.set_title("Sample bankrolls, start = 100")
    ax1.text(285, 12, "Tourist (median)", color=INK_2, fontsize=9)
    ax1.text(228, 245, "Shark (median)", color=INK_2, fontsize=9)

    # Bayesian and Shark both survive ~always; draw Bayesian wider underneath
    # so it stays visible where the curves coincide at 1.0
    widths = {"Tourist": 2.0, "Hedger": 2.0, "Bayesian": 4.5, "Shark": 2.0}
    for name, color in BOT_COLORS.items():
        alive = (paths[name] > 0).mean(axis=0)
        ax2.plot(t, alive, color=color, lw=widths[name], zorder=3)
    ax2.set_ylim(-0.03, 1.05)
    ax2.set_xlabel("rounds played")
    ax2.set_ylabel("P(bankroll still above 0)")
    ax2.set_title("Survival probability")
    ax2.legend(list(BOT_COLORS), loc="lower left")

    fig.tight_layout()
    save(fig, "ruin.png")


if __name__ == "__main__":
    main()
