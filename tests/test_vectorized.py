"""The numpy mirrors must agree with the scalar reference implementations."""

import pytest

np = pytest.importorskip("numpy")

from auction import AuctionConfig, bayes  # noqa: E402
from auction import vectorized as vec  # noqa: E402

CFG = AuctionConfig()
SIGNALS = np.linspace(-12.0, 112.0, 249)


@pytest.mark.parametrize("n", [1, 2, 5, 9])
def test_matches_scalar_reference(n):
    got_pm = vec.posterior_mean(SIGNALS, CFG)
    got_max = vec.max_signal_posterior_mean(SIGNALS, n, CFG)
    got_eq = vec.equilibrium_bid(SIGNALS, n, CFG)
    for i, s in enumerate(SIGNALS):
        s = float(s)
        assert got_pm[i] == pytest.approx(bayes.posterior_mean(s, CFG), abs=1e-9)
        assert got_max[i] == pytest.approx(bayes.max_signal_posterior_mean(s, n, CFG), abs=1e-9)
        assert got_eq[i] == pytest.approx(bayes.equilibrium_bid(s, n, CFG), abs=1e-9)


def test_settle_rounds_matches_engine_semantics():
    v = np.array([60.0, 30.0])
    bids = np.array([[50.0, 66.0, 58.0], [20.0, 10.0, 15.0]])
    winner, pnl = vec.settle_rounds(v, bids)
    assert winner.tolist() == [1, 0]
    assert pnl[0].tolist() == [0.0, -6.0, 0.0]
    assert pnl[1].tolist() == [10.0, 0.0, 0.0]


def test_interior_draws_stay_interior():
    rng = np.random.default_rng(0)
    v, signals = vec.draw_rounds(CFG, 4, 10_000, rng, interior_only=True)
    assert v.min() >= CFG.v_low + 2 * CFG.noise
    assert v.max() <= CFG.v_high - 2 * CFG.noise
    assert signals.min() >= CFG.v_low + CFG.noise
    assert signals.max() <= CFG.v_high - CFG.noise
