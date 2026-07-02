import math
import random

import pytest

from auction import AuctionConfig, Bayesian, Hedger, Shark, Tourist, equilibrium_bid
from auction.english import invert_dropout, pivotal_estimate, run_english

CFG = AuctionConfig()


class TestPivotalEstimate:
    def test_no_revelation_is_posterior_mean(self):
        # with nothing revealed the pivotal rule is the plain posterior mean
        assert pivotal_estimate(50.0, math.inf, CFG) == 50.0
        assert pivotal_estimate(5.0, math.inf, CFG) == 7.5

    def test_lowest_revealed_signal_caps_the_upside(self):
        # revealed low signal 40 caps V at 50, so the midpoint drops
        assert pivotal_estimate(60.0, 40.0, CFG) == pytest.approx(50.0)

    def test_inversion_roundtrip(self):
        for min_rev in (math.inf, 55.0, 30.0):
            for s in (20.0, 47.0, 80.0):
                p = pivotal_estimate(s, min_rev, CFG)
                s_back = invert_dropout(p, min_rev, CFG)
                assert pivotal_estimate(s_back, min_rev, CFG) == pytest.approx(p, abs=1e-6)


class TestMechanics:
    def test_two_tourists_lower_signal_drops_at_it(self):
        r = run_english(CFG, [Tourist(), Tourist()], random.Random(0),
                        true_value=50.0, signals=[44.0, 55.0])
        assert r.winner == 1
        assert r.price == 44.0
        assert r.dropouts[0].bidder == 0
        assert r.pnl == (0.0, 6.0)

    def test_all_shark_interior_price_is_midpoint_of_extreme_signals(self):
        signals = [48.0, 55.0, 61.0, 66.0]
        r = run_english(CFG, [Shark() for _ in range(4)], random.Random(1),
                        true_value=57.0, signals=signals)
        # exit order follows signals; winner pays (second-highest + lowest)/2
        assert [d.bidder for d in r.dropouts] == [0, 1, 2]
        assert r.winner == 3
        assert r.price == pytest.approx((61.0 + 48.0) / 2)
        # dropout prices invert back to the true signals
        for d in r.dropouts:
            assert d.inferred_signal == pytest.approx(signals[d.bidder], abs=1e-6)

    def test_identical_bidders_tie_cleanly(self):
        r = run_english(CFG, [Bayesian(), Bayesian(), Bayesian()], random.Random(3),
                        true_value=50.0, signals=[50.0, 50.0, 50.0])
        assert r.price == 50.0
        assert len(r.dropouts) == 2

    def test_prices_non_decreasing_and_settlement_consistent(self):
        rng = random.Random(9)
        lineup = [Tourist(), Hedger(), Bayesian(), Shark(), Shark()]
        for _ in range(500):
            r = run_english(CFG, lineup, rng)
            prices = [d.price for d in r.dropouts]
            assert all(a <= b for a, b in zip(prices, prices[1:], strict=False))
            assert len(r.dropouts) == len(lineup) - 1
            assert r.pnl[r.winner] == pytest.approx(r.true_value - r.price)
            assert sum(1 for p in r.pnl if p != 0.0) <= 1

    def test_player_seat_drop_and_stay(self):
        lineup = [Tourist(), Shark(), Shark()]
        kw = {"true_value": 50.0, "signals": [52.0, 47.0, 58.0]}
        # player (seat 0) drops immediately: recorded first at the clock floor
        r = run_english(CFG, lineup, random.Random(4), player_index=0,
                        player_drop=0.0, **kw)
        assert r.dropouts[0].bidder == 0
        assert r.pnl[0] == 0.0
        # player never drops: wins at the last bot's exit price
        r = run_english(CFG, lineup, random.Random(4), player_index=0,
                        player_drop=None, **kw)
        assert r.winner == 0
        assert r.pnl[0] == pytest.approx(50.0 - r.price)


class TestRevenue:
    def test_english_beats_sealed_revenue_with_sharks(self):
        """The linkage principle: dropout leakage raises seller revenue."""
        rng = random.Random(42)
        n, rounds = 5, 4_000
        english = sealed = 0.0
        counted = 0
        while counted < rounds:
            v = rng.uniform(CFG.v_low, CFG.v_high)
            if not (2 * CFG.noise <= v <= CFG.v_high - 2 * CFG.noise):
                continue
            signals = [v + rng.uniform(-CFG.noise, CFG.noise) for _ in range(n)]
            r = run_english(CFG, [Shark() for _ in range(n)], rng,
                            true_value=v, signals=signals)
            english += r.price
            sealed += max(equilibrium_bid(s, n, CFG) for s in signals)
            counted += 1
        assert english / rounds > sealed / rounds + 1.0
