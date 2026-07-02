"""Monte Carlo best-response check: no unilateral deviation beats the equilibrium.

One bidder shifts the equilibrium bid by a constant delta while the rest play
it straight. Common random numbers (the same value/signal draws for every
delta) make the EV comparison sharp. Rounds are conditioned on the interior
region (V in [2a, v_high - 2a]) where the closed form is exact.
"""

import random

import pytest

from auction import AuctionConfig, equilibrium_bid

CFG = AuctionConfig()
N = 5
DELTAS = (-5.0, -2.0, -1.0, 0.0, 1.0, 2.0, 5.0)


def deviation_evs(n_rounds: int, seed: int) -> dict[float, float]:
    rng = random.Random(seed)
    a = CFG.noise
    totals = dict.fromkeys(DELTAS, 0.0)
    done = 0
    while done < n_rounds:
        v = rng.uniform(CFG.v_low, CFG.v_high)
        if not (2 * a <= v <= CFG.v_high - 2 * a):
            continue
        signals = [v + rng.uniform(-a, a) for _ in range(N)]
        eq_bids = [equilibrium_bid(s, N, CFG) for s in signals]
        rival_best = max(eq_bids[1:])
        for delta in DELTAS:
            my_bid = eq_bids[0] + delta
            if my_bid > rival_best:
                totals[delta] += v - my_bid
        done += 1
    return {d: t / n_rounds for d, t in totals.items()}


@pytest.mark.slow
def test_equilibrium_is_a_best_response():
    evs = deviation_evs(n_rounds=150_000, seed=99)
    ev_eq = evs[0.0]
    assert ev_eq > 0.0
    # big deviations strictly hurt; small ones must not help beyond MC tolerance
    for delta in (-5.0, -2.0, 2.0, 5.0):
        assert evs[delta] < ev_eq
    assert max(evs.values()) <= ev_eq + 0.02
