"""Numpy mirrors of :mod:`auction.bayes` for Monte Carlo at scale.

Kept out of ``auction/__init__.py`` so the core package stays stdlib-only;
import this module explicitly when numpy is available. Consistency with the
scalar implementations is enforced by tests/test_vectorized.py.
"""

from __future__ import annotations

import numpy as np

from .engine import AuctionConfig


def posterior_bounds(signals: np.ndarray, cfg: AuctionConfig) -> tuple[np.ndarray, np.ndarray]:
    lo = np.maximum(cfg.v_low, signals - cfg.noise)
    hi = np.minimum(cfg.v_high, signals + cfg.noise)
    clamped = np.clip(signals, cfg.v_low, cfg.v_high)
    bad = lo > hi
    return np.where(bad, clamped, lo), np.where(bad, clamped, hi)


def posterior_mean(signals: np.ndarray, cfg: AuctionConfig) -> np.ndarray:
    lo, hi = posterior_bounds(signals, cfg)
    return (lo + hi) / 2


def max_signal_posterior_mean(
    signals: np.ndarray, n_bidders: int, cfg: AuctionConfig
) -> np.ndarray:
    a = cfg.noise
    n = n_bidders
    lo, hi = posterior_bounds(signals, cfg)
    u_lo = signals + a - hi
    u_hi = signals + a - lo
    den = u_hi**n - u_lo**n
    degenerate = (hi - lo) < 1e-12
    mean_u = np.where(
        degenerate,
        0.0,
        (n / (n + 1)) * (u_hi ** (n + 1) - u_lo ** (n + 1)) / np.where(degenerate, 1.0, den),
    )
    return np.where(degenerate, lo, signals + a - mean_u)


def equilibrium_bid(signals: np.ndarray, n_bidders: int, cfg: AuctionConfig) -> np.ndarray:
    a = cfg.noise
    interior_start = cfg.v_low + a
    e_max = max_signal_posterior_mean(signals, n_bidders, cfg)
    y = (2 * a / (n_bidders + 1)) * np.exp(
        -(n_bidders / (2 * a)) * np.maximum(signals - interior_start, 0.0)
    )
    return np.where(signals <= interior_start, e_max, np.minimum(signals - a + y, e_max))


def draw_rounds(
    cfg: AuctionConfig,
    n_bidders: int,
    n_rounds: int,
    rng: np.random.Generator,
    interior_only: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Values (n_rounds,) and signals (n_rounds, n_bidders).

    ``interior_only`` draws V from [v_low + 2a, v_high - 2a], the region where
    every signal lands where the closed-form interior formulas are exact.
    """
    a = cfg.noise
    lo, hi = (cfg.v_low + 2 * a, cfg.v_high - 2 * a) if interior_only else (cfg.v_low, cfg.v_high)
    v = rng.uniform(lo, hi, size=n_rounds)
    signals = v[:, None] + rng.uniform(-a, a, size=(n_rounds, n_bidders))
    return v, signals


def settle_rounds(v: np.ndarray, bids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Winner index and full PnL matrix for a (n_rounds, n_bidders) bid array."""
    winner = np.argmax(bids, axis=1)
    rows = np.arange(len(v))
    pnl = np.zeros_like(bids)
    pnl[rows, winner] = v - bids[rows, winner]
    return winner, pnl
