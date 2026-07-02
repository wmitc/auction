"""What winning feels like, strategy by strategy.

Each bot plays hero against four Sharks. The histogram shows the hero's PnL
on the rounds it *wins* — the Tourist's wins are mostly losses (that's the
curse), the Bayesian centers on zero, the Shark's wins are paid for.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from style import BOT_COLORS, INK_2, MUTED, apply_style, save

from auction import AuctionConfig
from auction.vectorized import (
    draw_rounds,
    equilibrium_bid,
    max_signal_posterior_mean,
    posterior_mean,
)

ROUNDS = 500_000
N = 5  # hero + 4 sharks


def hero_bids(name: str, signals: np.ndarray, cfg: AuctionConfig) -> np.ndarray:
    if name == "Tourist":
        return np.clip(signals, cfg.v_low, cfg.v_high)
    if name == "Hedger":
        return 0.9 * posterior_mean(signals, cfg)
    if name == "Bayesian":
        return max_signal_posterior_mean(signals, N, cfg)
    return equilibrium_bid(signals, N, cfg)


def main() -> None:
    apply_style()
    cfg = AuctionConfig()
    rng = np.random.default_rng(7)
    v, signals = draw_rounds(cfg, N, ROUNDS, rng)
    shark_bids = equilibrium_bid(signals[:, 1:], N, cfg)
    rival_best = shark_bids.max(axis=1)

    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    bins = np.linspace(-22, 14, 73)
    stats_lines = []
    for name, color in BOT_COLORS.items():
        mine = hero_bids(name, signals[:, 0], cfg)
        win = mine > rival_best
        pnl_win = (v - mine)[win]
        ax.hist(pnl_win, bins=bins, density=True, histtype="step", color=color, lw=2, zorder=3)
        stats_lines.append(
            f"{name:<9} wins {win.mean():>4.0%} of rounds, "
            f"PnL/round {pnl_win.sum() / ROUNDS:+.2f}"
        )

    ax.axvline(0, color=MUTED, lw=1, zorder=2)
    # direct labels near each mode, in ink with a colored key
    modes = {"Tourist": (-9.3, 0.089), "Hedger": (-6.6, 0.028), "Bayesian": (1.4, 0.095),
             "Shark": (4.9, 0.070)}
    box = {"fc": "#fcfcfb", "lw": 1.2, "boxstyle": "round,pad=0.25"}
    for name, (x, y) in modes.items():
        ax.text(x, y, name, color=INK_2, fontsize=9, bbox={**box, "ec": BOT_COLORS[name]})
    ax.text(
        0.02, 0.97, "\n".join(stats_lines), transform=ax.transAxes, va="top",
        color=INK_2, fontsize=8.5, family="monospace",
    )
    ax.set_xlabel("PnL on rounds you win  (V − your bid)")
    ax.set_ylabel("density")
    ax.set_title("Against four Sharks: what each strategy's wins are worth")
    fig.tight_layout()
    save(fig, "pnl_dist.png")


if __name__ == "__main__":
    main()
