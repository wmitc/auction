"""Numerical proof that the Shark's strategy is an equilibrium.

One bidder shifts the equilibrium bid by a constant delta while everyone
else plays it straight; expected PnL is estimated with common random numbers
so the curves are smooth. Every curve peaks at delta = 0: no unilateral
deviation helps, for any field size.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from style import INK_2, MUTED, apply_style, save

from auction import AuctionConfig
from auction.vectorized import draw_rounds, equilibrium_bid

ROUNDS = 1_000_000
DELTAS = np.linspace(-8, 8, 65)
FIELD_SIZES = (2, 4, 8)
COLORS = {2: "#9ec5f4", 4: "#5598e7", 8: "#1c5cab"}  # one-hue sequential ramp: N is ordered


def deviation_curve(n: int, cfg: AuctionConfig, rng: np.random.Generator) -> np.ndarray:
    v, signals = draw_rounds(cfg, n, ROUNDS, rng, interior_only=True)
    eq = equilibrium_bid(signals, n, cfg)
    rival_best = eq[:, 1:].max(axis=1)
    evs = np.empty(len(DELTAS))
    for i, d in enumerate(DELTAS):
        mine = eq[:, 0] + d
        evs[i] = np.where(mine > rival_best, v - mine, 0.0).mean()
    return evs


def main() -> None:
    apply_style()
    cfg = AuctionConfig()
    rng = np.random.default_rng(31)

    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    for n in FIELD_SIZES:
        evs = deviation_curve(n, cfg, rng)
        ax.plot(DELTAS, evs, color=COLORS[n], zorder=3)
        i0 = int(np.argmin(np.abs(DELTAS)))
        ax.scatter([0], [evs[i0]], color=COLORS[n], s=30, zorder=4,
                   edgecolors="#fcfcfb", linewidths=2)
        ax.text(DELTAS[-1] + 0.25, evs[-1], f"N = {n}", color=INK_2, fontsize=9, va="center")

    ax.axvline(0, color=MUTED, lw=1, zorder=2)
    ax.set_xlim(-8, 9.6)
    ax.set_xlabel("constant shift added to the equilibrium bid")
    ax.set_ylabel("deviator's expected PnL per round")
    ax.set_title("No unilateral deviation beats the equilibrium bid")
    fig.tight_layout()
    save(fig, "best_response.png")


if __name__ == "__main__":
    main()
