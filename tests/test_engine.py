import random

import pytest

from auction import AuctionConfig, Shark, Tourist, draw_round, run_round, settle

CFG = AuctionConfig()


class TestDrawRound:
    def test_reproducible_given_seed(self):
        v1, s1 = draw_round(CFG, 5, random.Random(42))
        v2, s2 = draw_round(CFG, 5, random.Random(42))
        assert (v1, s1) == (v2, s2)

    def test_signals_within_noise_band(self):
        rng = random.Random(7)
        for _ in range(500):
            v, signals = draw_round(CFG, 4, rng)
            assert CFG.v_low <= v <= CFG.v_high
            assert all(abs(s - v) <= CFG.noise for s in signals)

    def test_rejects_zero_bidders(self):
        with pytest.raises(ValueError):
            draw_round(CFG, 0, random.Random(0))


class TestSettle:
    def test_highest_bid_wins_and_pays_its_bid(self):
        r = settle(60.0, [55.0, 70.0, 65.0], [50.0, 66.0, 58.0], random.Random(0))
        assert r.winner == 1
        assert r.price == 66.0
        assert r.pnl == (0.0, -6.0, 0.0)

    def test_losers_book_zero(self):
        r = settle(30.0, [28.0, 35.0], [20.0, 25.0], random.Random(0))
        assert sum(1 for p in r.pnl if p != 0.0) <= 1

    def test_tie_broken_among_top_bidders(self):
        winners = {
            settle(50.0, [50.0, 50.0, 50.0], [40.0, 40.0, 30.0], random.Random(seed)).winner
            for seed in range(50)
        }
        assert winners == {0, 1}

    def test_mismatched_lengths_rejected(self):
        with pytest.raises(ValueError):
            settle(50.0, [50.0], [40.0, 41.0], random.Random(0))


class TestRunRound:
    def test_full_round_is_deterministic(self):
        bots = [Tourist(), Shark(), Shark()]
        r1 = run_round(CFG, bots, random.Random(123))
        r2 = run_round(CFG, bots, random.Random(123))
        assert r1 == r2

    def test_pnl_settles_against_true_value(self):
        r = run_round(CFG, [Tourist(), Shark()], random.Random(5))
        assert r.pnl[r.winner] == pytest.approx(r.true_value - r.price)


class TestConfigValidation:
    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError):
            AuctionConfig(v_low=10, v_high=5)

    def test_rejects_noise_wider_than_range(self):
        with pytest.raises(ValueError):
            AuctionConfig(v_low=0, v_high=10, noise=6)
