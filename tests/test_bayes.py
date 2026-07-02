import itertools
import math

import pytest

from auction import AuctionConfig, equilibrium_bid, max_signal_posterior_mean, posterior_mean

CFG = AuctionConfig()  # V ~ U(0, 100), noise a = 10


def numeric_max_signal_mean(
    signal: float, n: int, cfg: AuctionConfig, steps: int = 200_000
) -> float:
    """Midpoint-rule integration of the tilted posterior, as an independent check.

    Density on [lo, hi] is proportional to (s + a - v)^(n-1).
    """
    lo = max(cfg.v_low, signal - cfg.noise)
    hi = min(cfg.v_high, signal + cfg.noise)
    h = (hi - lo) / steps
    num = den = 0.0
    for i in range(steps):
        v = lo + (i + 0.5) * h
        w = (signal + cfg.noise - v) ** (n - 1)
        num += v * w
        den += w
    return num / den


class TestPosteriorMean:
    def test_interior_is_signal(self):
        assert posterior_mean(50.0, CFG) == 50.0

    def test_low_boundary_truncates(self):
        assert posterior_mean(5.0, CFG) == pytest.approx(7.5)  # U(0, 15)

    def test_high_boundary_truncates(self):
        assert posterior_mean(95.0, CFG) == pytest.approx(92.5)  # U(85, 100)

    def test_signal_below_feasible_range(self):
        assert posterior_mean(-15.0, CFG) == 0.0


class TestMaxSignalPosteriorMean:
    def test_interior_closed_form(self):
        # E[V | s, s = max of n] = s - a (n-1)/(n+1) in the interior
        for n in (1, 2, 4, 8):
            expected = 50.0 - 10.0 * (n - 1) / (n + 1)
            assert max_signal_posterior_mean(50.0, n, CFG) == pytest.approx(expected)

    def test_n1_reduces_to_posterior_mean(self):
        for s in (-5.0, 3.0, 50.0, 97.0, 104.0):
            assert max_signal_posterior_mean(s, 1, CFG) == pytest.approx(posterior_mean(s, CFG))

    @pytest.mark.parametrize("signal", [3.0, 9.9, 50.0, 93.0, 105.0])
    @pytest.mark.parametrize("n", [2, 5])
    def test_matches_numeric_integration_with_truncation(self, signal, n):
        got = max_signal_posterior_mean(signal, n, CFG)
        want = numeric_max_signal_mean(signal, n, CFG)
        assert got == pytest.approx(want, abs=1e-3)

    def test_more_bidders_means_bigger_correction(self):
        means = [max_signal_posterior_mean(50.0, n, CFG) for n in range(1, 10)]
        assert all(a > b for a, b in itertools.pairwise(means))


class TestEquilibriumBid:
    def test_interior_is_roughly_signal_minus_a(self):
        b = equilibrium_bid(50.0, 4, CFG)
        y = (20 / 5) * math.exp(-(4 / 20) * 40.0)
        assert b == pytest.approx(40.0 + y)
        assert b == pytest.approx(40.0, abs=0.01)

    def test_continuous_at_interior_boundary(self):
        for n in (2, 4, 8):
            below = equilibrium_bid(10.0 - 1e-9, n, CFG)
            above = equilibrium_bid(10.0 + 1e-9, n, CFG)
            assert below == pytest.approx(above, abs=1e-6)
            # at s = v_low + a the equilibrium bid equals the zero-margin bid
            assert above == pytest.approx(max_signal_posterior_mean(10.0, n, CFG), abs=1e-6)

    def test_never_exceeds_curse_corrected_estimate(self):
        for n in (2, 4, 8):
            for s in (-5.0, 2.0, 10.0, 30.0, 70.0, 95.0, 108.0):
                assert equilibrium_bid(s, n, CFG) <= max_signal_posterior_mean(s, n, CFG) + 1e-12

    def test_shading_grows_with_competition(self):
        # counterintuitive core lesson: more rivals => bid *less* for the same signal
        bids = [equilibrium_bid(60.0, n, CFG) for n in (2, 4, 8)]
        assert bids[0] > bids[1] > bids[2]
