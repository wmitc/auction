"""The winner's curse in one picture: the winning signal overshoots V.

Left: overshoot E[s_max - V] against the number of bidders, Monte Carlo vs
the closed form a(N-1)/(N+1). Right: overshoot against the noise half-width.
Draws are interior-conditioned so the closed form applies exactly.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from style import ACCENT, INK_2, MUTED, THEORY, apply_style, save

from auction import AuctionConfig
from auction.vectorized import draw_rounds

ROUNDS = 400_000


def overshoot(cfg: AuctionConfig, n: int, rng: np.random.Generator) -> float:
    v, signals = draw_rounds(cfg, n, ROUNDS, rng, interior_only=True)
    return float((signals.max(axis=1) - v).mean())


def main() -> None:
    apply_style()
    rng = np.random.default_rng(2026)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.9))

    ns = np.arange(1, 11)
    cfg = AuctionConfig()
    mc = [overshoot(cfg, int(n), rng) for n in ns]
    theory_n = cfg.noise * (ns - 1) / (ns + 1)
    ax1.plot(ns, theory_n, color=THEORY, zorder=2)
    ax1.scatter(ns, mc, color=ACCENT, s=26, zorder=3)
    ax1.set_xlabel("number of bidders N")
    ax1.set_ylabel("E[winning signal − V]")
    ax1.set_title("More rivals, more optimistic winning signal")
    ax1.set_xticks(ns)
    ax1.text(6.1, cfg.noise * 5 / 7 - 1.7, "a(N−1)/(N+1)", color=INK_2, fontsize=9, rotation=8)
    ax1.text(2.0, 4.4, "Monte Carlo", color=ACCENT, fontsize=9)

    widths = np.array([2.0, 5.0, 10.0, 15.0, 20.0])
    n = 5
    mc_w = [overshoot(AuctionConfig(noise=a), n, rng) for a in widths]
    ax2.plot(widths, widths * (n - 1) / (n + 1), color=THEORY, zorder=2)
    ax2.scatter(widths, mc_w, color=ACCENT, s=26, zorder=3)
    ax2.set_xlabel("signal noise half-width a")
    ax2.set_ylabel("E[winning signal − V]")
    ax2.set_title(f"Noisier signals, bigger curse (N = {n})")
    ax2.text(12.3, 7.2, "a(N−1)/(N+1)", color=INK_2, fontsize=9, rotation=22)

    for ax in (ax1, ax2):
        ax.tick_params(color=MUTED)
    fig.tight_layout()
    save(fig, "curse.png")


if __name__ == "__main__":
    main()
