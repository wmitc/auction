import itertools

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from web.app import ARENA_LINEUP, app  # noqa: E402

client = TestClient(app)


def new_arena(seed=99) -> str:
    resp = client.post(f"/api/english/session?seed={seed}")
    assert resp.status_code == 200
    return resp.json()["session_id"]


def start_round(sid: str) -> dict:
    resp = client.post(f"/api/english/{sid}/round")
    assert resp.status_code == 200
    return resp.json()


def test_round_schedule_is_a_valid_clock():
    sid = new_arena()
    r = start_round(sid)
    assert r["n_bidders"] == len(ARENA_LINEUP) + 1
    prices = [e["price"] for e in r["events"]]
    assert len(prices) == len(ARENA_LINEUP)  # every bot eventually drops if you stay
    assert all(a <= b for a, b in itertools.pairwise(prices))
    assert r["win_price"] == prices[-1]
    # hints only ever move down as low signals are revealed
    hints = [r["your_hint_start"]] + [e["your_hint_after"] for e in r["events"]]
    assert all(a >= b for a, b in itertools.pairwise(hints))


def test_drop_immediately_books_zero():
    sid = new_arena()
    start_round(sid)
    resp = client.post(f"/api/english/{sid}/drop", json={"price": 0.0}).json()
    a = resp["autopsy"]
    assert a["your_pnl"] == 0.0
    assert not a["you_won"]
    assert a["timeline"][0]["is_you"]
    assert resp["bankroll"] == 100.0


def test_staying_to_the_end_wins_at_the_scheduled_price():
    sid = new_arena(seed=7)
    r = start_round(sid)
    resp = client.post(f"/api/english/{sid}/drop", json={"price": None}).json()
    a = resp["autopsy"]
    assert a["you_won"]
    assert a["price"] == pytest.approx(r["win_price"], abs=0.02)
    assert a["your_pnl"] == pytest.approx(a["true_value"] - a["price"], abs=0.02)
    assert "shadow_shark" in a


def test_clock_state_machine():
    sid = new_arena()
    assert client.post(f"/api/english/{sid}/drop", json={"price": 5}).status_code == 409
    start_round(sid)
    assert client.post(f"/api/english/{sid}/round").status_code == 409
    assert client.post(f"/api/english/{sid}/drop", json={"price": 5}).status_code == 200
