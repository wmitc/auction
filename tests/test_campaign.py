from auction import AuctionConfig
from auction.campaign import LEVELS, STARTING_BANKROLL, level_status, shark_benchmark

CFG = AuctionConfig()


def test_levels_are_numbered_and_ramp_up():
    assert [lvl.number for lvl in LEVELS] == list(range(1, len(LEVELS) + 1))
    assert len(LEVELS[0].opponents) == 1
    assert all(len(lvl.opponents) >= 1 for lvl in LEVELS)
    # the finale is the 8-shark table
    assert len(LEVELS[-1].opponents) == 8
    assert {b.name for b in LEVELS[-1].opponents} == {"Shark"}


def test_level_status_transitions():
    lvl = LEVELS[0]
    assert level_status(STARTING_BANKROLL, 0, lvl) == "playing"
    assert level_status(0.0, 3, lvl) == "busted"
    assert level_status(-5.0, 3, lvl) == "busted"
    assert level_status(STARTING_BANKROLL + 10, lvl.rounds, lvl) == "passed"
    assert level_status(STARTING_BANKROLL - 10, lvl.rounds, lvl) == "failed"
    assert level_status(STARTING_BANKROLL, lvl.rounds, lvl) == "failed"


def test_shark_benchmark_is_positive_everywhere():
    # a Shark in the player's seat never has negative EV against any lineup
    for lvl in LEVELS:
        assert shark_benchmark(lvl, CFG, seed=1, n_rounds=4_000) > 0
