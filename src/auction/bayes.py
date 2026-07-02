"""Posterior calculations and the equilibrium bid for the common-value model.

Model: V ~ Uniform(v_low, v_high), signal s = V + eps, eps ~ Uniform(-a, a).

Key facts (derived in the README, verified in tests and by Monte Carlo):

* Posterior: V | s ~ Uniform(max(v_low, s - a), min(v_high, s + a)).
* Winner's-curse correction: conditioning on s being the *highest* of n
  signals tilts the posterior density by P(other signal <= s | V)^(n-1),
  which is proportional to (s - V + a)^(n-1) where it is interior. In the
  interior this gives E[V | s, s = max of n] = s - a(n-1)/(n+1).
* Symmetric risk-neutral Nash equilibrium (Kagel-Levin form), for signals in
  the interior region s >= v_low + a:

      b(s) = s - a + Y(s),   Y(s) = (2a / (n+1)) * exp(-(n / 2a) (s - v_low - a))

  so away from the low boundary the equilibrium bid is essentially s - a: you
  bid as if your noise draw were maximally unlucky, and the winner keeps an
  information rent of about 2a/(n+1) per win.
"""

from __future__ import annotations

import math

from .engine import AuctionConfig


def posterior_bounds(signal: float, cfg: AuctionConfig) -> tuple[float, float]:
    """Support of V given one signal (uniform prior, uniform noise)."""
    lo = max(cfg.v_low, signal - cfg.noise)
    hi = min(cfg.v_high, signal + cfg.noise)
    if lo > hi:  # signal outside the feasible range; clamp to the nearest edge
        lo = hi = min(max(signal, cfg.v_low), cfg.v_high)
    return lo, hi


def posterior_mean(signal: float, cfg: AuctionConfig) -> float:
    """E[V | s]: midpoint of the truncated uniform posterior."""
    lo, hi = posterior_bounds(signal, cfg)
    return (lo + hi) / 2


def max_signal_posterior_mean(signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
    """E[V | s, s is the highest of n signals] — the winner's-curse correction.

    On [lo, hi] the conditional density is proportional to (s + a - V)^(n-1).
    With u = s + a - V the density is u^(n-1) on [u_lo, u_hi], whose mean is
    (n/(n+1)) (u_hi^(n+1) - u_lo^(n+1)) / (u_hi^n - u_lo^n). Exact including
    boundary truncation; reduces to s - a(n-1)/(n+1) in the interior and to
    the plain posterior mean for n = 1.
    """
    if n_bidders < 1:
        raise ValueError("need at least one bidder")
    a = cfg.noise
    lo, hi = posterior_bounds(signal, cfg)
    if hi - lo < 1e-12:
        return lo
    n = n_bidders
    u_lo = signal + a - hi
    u_hi = signal + a - lo
    mean_u = (n / (n + 1)) * (u_hi ** (n + 1) - u_lo ** (n + 1)) / (u_hi**n - u_lo**n)
    return signal + a - mean_u


def equilibrium_bid(signal: float, n_bidders: int, cfg: AuctionConfig) -> float:
    """Symmetric RNNE bid (interior Kagel-Levin form, continuous extension at edges).

    Below the interior region (s < v_low + a) the interior formula meets the
    zero-margin bid E[V | s, s = max] exactly at s = v_low + a, so we extend
    with that. At the top we never bid above the curse-corrected estimate.
    """
    a = cfg.noise
    interior_start = cfg.v_low + a
    e_max = max_signal_posterior_mean(signal, n_bidders, cfg)
    if signal <= interior_start:
        return e_max
    y = (2 * a / (n_bidders + 1)) * math.exp(-(n_bidders / (2 * a)) * (signal - interior_start))
    return min(signal - a + y, e_max)
