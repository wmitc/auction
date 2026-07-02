"""Common-value auction game: engine, Bayesian math, and bidder strategies."""

from .bayes import equilibrium_bid, max_signal_posterior_mean, posterior_mean
from .bots import Bayesian, Hedger, Shark, Tourist
from .engine import AuctionConfig, RoundResult, draw_round, run_round, settle

__all__ = [
    "AuctionConfig",
    "RoundResult",
    "draw_round",
    "run_round",
    "settle",
    "posterior_mean",
    "max_signal_posterior_mean",
    "equilibrium_bid",
    "Tourist",
    "Hedger",
    "Bayesian",
    "Shark",
]
