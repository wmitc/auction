"""Revenue equivalence breaking under common values (the linkage principle).

All-Shark fields, interior-conditioned. In the sealed first-price auction
the winner keeps a rent of about 2a/(N+1); in the English clock auction the
dropout prices leak the low signals, the price tracks the information, and
the winner's rent is halved to about a/(N+1) — the seller pockets the rest.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from style import ACCENT, INK_2, THEORY, apply_style, save

from auction import AuctionConfig
from auction.vectorized import draw_rounds, equilibrium_bid

SEALED_COLOR = "#2a78d6"
ENGLISH_COLOR = ACCENT
ROUNDS = 300_000
NS = np.arange(2, 9)


def rents(n: int, cfg: AuctionConfig, rng: np.random.Generator) -> tuple[float, float]:
    v, signals = draw_rounds(cfg, n, ROUNDS, rng, interior_only=True)
    sealed_price = equilibrium_bid(signals, n, cfg).max(axis=1)
    s_sorted = np.sort(signals, axis=1)
    # all-Shark English clock, interior: winner pays (second-highest + lowest)/2
    # (verified against the sequential engine in tests/test_english.py)
    english_price = (s_sorted[:, -2] + s_sorted[:, 0]) / 2
    return float((v - sealed_price).mean()), float((v - english_price).mean())


def main() -> None:
    apply_style()
    cfg = AuctionConfig()
    rng = np.random.default_rng(17)
    a = cfg.noise

    pairs = [rents(int(n), cfg, rng) for n in NS]
    sealed = [p[0] for p in pairs]
    english = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(NS, 2 * a / (NS + 1), color=THEORY, lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.plot(NS, a / (NS + 1), color=THEORY, lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.plot(NS, sealed, color=SEALED_COLOR, zorder=3)
    ax.plot(NS, english, color=ENGLISH_COLOR, zorder=3)

    ax.text(8.15, sealed[-1], "sealed first-price\nrent ≈ 2a/(N+1)", color=INK_2,
            fontsize=9, va="center")
    ax.text(8.15, english[-1], "English clock\nrent ≈ a/(N+1)", color=INK_2,
            fontsize=9, va="center")
    ax.set_xlim(2, 9.7)
    ax.set_xticks(NS)
    ax.set_xlabel("number of bidders N")
    ax.set_ylabel("winner's expected profit per auction")
    ax.set_title("Dropout leakage halves the winner's rent (all-Shark fields)")
    fig.tight_layout()
    save(fig, "revenue.png")


if __name__ == "__main__":
    main()
