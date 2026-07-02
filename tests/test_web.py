import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from web.app import app  # noqa: E402

from auction import AuctionConfig, equilibrium_bid  # noqa: E402
from auction.campaign import LEVELS, STARTING_BANKROLL  # noqa: E402

CFG = AuctionConfig()
client = TestClient(app)


def new_session(seed=1234) -> str:
    resp = client.post(f"/api/session?seed={seed}")
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_round_flow_and_autopsy_consistency():
    sid = new_session()
    r = client.post(f"/api/session/{sid}/round").json()
    assert r["status"] == "awaiting_bid"
    signal = r["your_signal"]
    n = r["n_bidders"]
    assert n == len(LEVELS[0].opponents) + 1

    bid = signal  # play the Tourist
    resp = client.post(f"/api/session/{sid}/bid", json={"bid": bid}).json()
    a = resp["autopsy"]
    assert a["shading_gap"] == pytest.approx(bid - equilibrium_bid(signal, n, CFG), abs=0.02)
    you = next(e for e in a["entries"] if e["is_you"])
    assert you["bid"] == pytest.approx(bid, abs=0.01)
    if a["you_won"]:
        assert a["your_pnl"] == pytest.approx(a["true_value"] - bid, abs=0.02)
    else:
        assert a["your_pnl"] == 0.0
    assert resp["bankroll"] == pytest.approx(STARTING_BANKROLL + a["your_pnl"], abs=0.02)
    assert resp["rounds_played"] == 1


def test_cannot_bid_without_a_round_or_deal_twice():
    sid = new_session()
    assert client.post(f"/api/session/{sid}/bid", json={"bid": 50}).status_code == 409
    assert client.post(f"/api/session/{sid}/round").status_code == 200
    assert client.post(f"/api/session/{sid}/round").status_code == 409


def test_unknown_session_is_404():
    assert client.post("/api/session/nope/round").status_code == 404


def test_absurd_bid_rejected():
    sid = new_session()
    client.post(f"/api/session/{sid}/round")
    assert client.post(f"/api/session/{sid}/bid", json={"bid": 900}).status_code == 422


def play_level(sid: str, shade: float) -> dict:
    """Bid signal - shade every round until the level resolves."""
    resp = None
    for _ in range(200):
        r = client.post(f"/api/session/{sid}/round")
        if r.status_code != 200:
            break
        signal = r.json()["your_signal"]
        bid = max(-9.9, min(109.9, signal - shade))
        resp = client.post(f"/api/session/{sid}/bid", json={"bid": bid}).json()
        if resp["status"] != "playing":
            break
    assert resp is not None
    return resp


def test_passing_a_level_unlocks_strategies_and_score():
    # equilibrium-ish shading against one Tourist should pass most seeds; find one
    for seed in range(25):
        sid = new_session(seed=seed)
        resp = play_level(sid, shade=9.0)
        if resp["status"] == "passed":
            break
    else:
        pytest.fail("no seed passed level 1 with near-equilibrium play")
    assert "level_score" in resp
    assert resp["bot_strategies"], "passing must reveal opponent strategies"
    nxt = client.post(f"/api/session/{sid}/advance").json()
    assert nxt["level"]["number"] == 2
    assert nxt["bankroll"] == STARTING_BANKROLL
    assert nxt["status"] == "playing"


def test_busting_requires_restart():
    # bidding way above any signal hemorrhages money against tourists
    for seed in range(25):
        sid = new_session(seed=seed)
        resp = play_level(sid, shade=-40.0)
        if resp["status"] == "busted":
            break
    else:
        pytest.fail("no seed busted despite bidding signal + 40")
    assert client.post(f"/api/session/{sid}/round").status_code == 409
    after = client.post(f"/api/session/{sid}/restart").json()
    assert after["bankroll"] == STARTING_BANKROLL
    assert after["rounds_played"] == 0
    assert after["status"] == "playing"
