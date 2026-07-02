"""Monte Carlo property tests: the strategies rank the way the theory says."""

import random

from auction import AuctionConfig, Bayesian, Hedger, Shark, Tourist, run_round

CFG = AuctionConfig()


def mean_pnl_per_round(bots, n_rounds: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    totals = [0.0] * len(bots)
    for _ in range(n_rounds):
        r = run_round(CFG, bots, rng)
        for i, p in enumerate(r.pnl):
            totals[i] += p
    return [t / n_rounds for t in totals]


def test_tourist_bleeds_money_against_sharks():
    pnl = mean_pnl_per_round([Tourist()] + [Shark() for _ in range(4)], 20_000, seed=1)
    assert pnl[0] < -1.0  # the winner's curse in one number


def test_tourists_lose_even_against_each_other():
    pnl = mean_pnl_per_round([Tourist() for _ in range(5)], 20_000, seed=2)
    assert sum(pnl) / len(pnl) < -1.0


def test_bayesian_is_calibrated_against_itself():
    # zero-margin curse-corrected bidding: winner's estimate is unbiased, EV ~ 0
    rng = random.Random(3)
    bots = [Bayesian() for _ in range(5)]
    err_sum = 0.0
    n_rounds = 20_000
    for _ in range(n_rounds):
        r = run_round(CFG, bots, rng)
        err_sum += r.true_value - r.price  # winner paid exactly their estimate
    assert abs(err_sum / n_rounds) < 0.25


def test_shark_earns_positive_rent_in_symmetric_field():
    pnl = mean_pnl_per_round([Shark() for _ in range(5)], 20_000, seed=4)
    assert all(p > 0.1 for p in pnl)


def test_shark_feasts_on_tourists():
    pnl = mean_pnl_per_round([Shark(), Tourist(), Tourist(), Tourist()], 20_000, seed=5)
    assert pnl[0] > 0.0
    assert all(p < 0.0 for p in pnl[1:])


def test_hedger_beats_tourist_but_not_shark():
    pnl = mean_pnl_per_round([Tourist(), Hedger(), Shark(), Shark()], 30_000, seed=6)
    tourist, hedger, shark = pnl[0], pnl[1], (pnl[2] + pnl[3]) / 2
    assert tourist < hedger < shark


def test_describe_exists_for_all_bots():
    for bot in (Tourist(), Hedger(), Bayesian(), Shark()):
        assert bot.name
        assert len(bot.describe()) > 20
