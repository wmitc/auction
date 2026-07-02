"""Shared matplotlib styling for the README figures.

Colors are the validated reference palette from the dataviz method: fixed
categorical slots per bot (color follows the entity), recessive hairline
grid, text in ink tokens rather than series colors.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# fixed categorical slots, one per bot, never reassigned
BOT_COLORS = {
    "Tourist": "#2a78d6",  # blue
    "Hedger": "#1baf7a",  # aqua
    "Bayesian": "#eda100",  # yellow
    "Shark": "#008300",  # green
}
ACCENT = "#4a3aa7"  # violet, for non-bot series
THEORY = MUTED  # reference/theory lines stay recessive

FIGURES_DIR = Path(__file__).resolve().parent.parent / "docs" / "figures"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
            "font.family": "sans-serif",
            "font.size": 10,
            "text.color": INK,
            "axes.edgecolor": BASELINE,
            "axes.linewidth": 1.0,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "axes.titlesize": 11,
            "axes.titleweight": "semibold",
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "lines.linewidth": 2.0,
            "lines.solid_joinstyle": "round",
            "lines.solid_capstyle": "round",
            "legend.frameon": False,
            "legend.fontsize": 9,
        }
    )


def save(fig, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path)
    plt.close(fig)
    print(f"wrote {path}")
    return path
