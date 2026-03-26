import pytest


@pytest.mark.skipif(True, reason="Requires real LLM API key and /sessions endpoint")
def test_chat_booking_flow(client):
    r = client.post("/chat", json={"session_id": "s1", "message": "Please book a room for Mina in the crypt"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "Booked!" in data["reply"]
    r2 = client.get(f"/sessions/{data['session_id']}")
    assert r2.status_code == 200
    msgs = r2.json()["messages"]
    assert any(m["role"] == "user" for m in msgs)
