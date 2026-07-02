"""How much to shade below the naive estimate E[V | s], as a function of N.

Two closed-form curves at an interior signal: the pure curse correction
(what the item is worth given you won) and the full equilibrium shade
(correction + profit margin). The gap between them is the winner's
information rent, about 2a/(N+1) per win.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from style import BOT_COLORS, INK_2, apply_style, save

from auction import AuctionConfig, equilibrium_bid, max_signal_posterior_mean, posterior_mean

SIGNAL = 50.0


def main() -> None:
    apply_style()
    cfg = AuctionConfig()
    ns = np.arange(2, 11)
    naive = posterior_mean(SIGNAL, cfg)
    curse_shade = np.array(
        [naive - max_signal_posterior_mean(SIGNAL, int(n), cfg) for n in ns]
    )
    eq_shade = np.array([naive - equilibrium_bid(SIGNAL, int(n), cfg) for n in ns])

    fig, ax = plt.subplots(figsize=(6.6, 4.1))
    ax.plot(ns, curse_shade, color=BOT_COLORS["Bayesian"], zorder=3)
    ax.plot(ns, eq_shade, color=BOT_COLORS["Shark"], zorder=3)
    ax.fill_between(ns, curse_shade, eq_shade, color=BOT_COLORS["Shark"], alpha=0.10, zorder=2)

    ax.text(10.05, curse_shade[-1], "curse correction\na(N−1)/(N+1)", color=INK_2,
            fontsize=9, va="center")
    ax.text(10.05, eq_shade[-1], "equilibrium shade\n≈ a", color=INK_2, fontsize=9, va="center")
    mid = 4
    ax.annotate(
        "your margin ≈ 2a/(N+1)",
        xy=(mid, (curse_shade[mid - 2] + eq_shade[mid - 2]) / 2),
        xytext=(5.4, 4.6),
        color=INK_2,
        fontsize=9,
        arrowprops={"arrowstyle": "-", "color": INK_2, "lw": 0.8},
    )

    ax.set_xlim(2, 12.3)
    ax.set_xticks(ns)
    ax.set_ylim(0, 11)
    ax.set_xlabel("number of bidders N")
    ax.set_ylabel(f"shade below E[V | s]  (a = {cfg.noise:.0f})")
    ax.set_title("Shade more as competition grows — then a bit more for profit")
    fig.tight_layout()
    save(fig, "shading.png")


if __name__ == "__main__":
    main()
