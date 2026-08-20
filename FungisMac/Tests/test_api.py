

def test_a_deleted_room_stays_deleted_across_restarts(tmp_path):
    """부팅 때 만드는 것이 보관 처리를 못 봤다.

    지워도 다음 부팅에 살아 돌아왔고, 앱은 그 방을 가리킨 채 떴다 — 헤더에는
    이름이 보이는데 좌측 목록에서는 아무것도 안 골라져 있었다.
    """
    database = tmp_path / "api.db"
    app = create_app(database)
    with TestClient(app) as client:
        assert any(p["id"] == "local" for p in client.get("/v1/projects").json())
        assert client.delete("/v1/projects/local").status_code == 200
        assert not any(p["id"] == "local" for p in client.get("/v1/projects").json())

    # 서버를 새로 띄운다. 지운 것은 지운 채로 있어야 한다.
    with TestClient(create_app(database)) as client:
        rooms = client.get("/v1/projects").json()
        assert not any(p["id"] == "local" for p in rooms)
        # HQ 는 항상 있다. 앱이 떨어질 자리다.
        assert any(p["id"] == "hq" for p in rooms)


def test_an_old_message_does_not_resurrect_its_room(tmp_path):
    """옛 글이 남아 있다고 방을 되살리지 않는다. 글은 history 로 읽힌다."""
    database = tmp_path / "api.db"
    app = create_app(database)
    with TestClient(app) as client:
        client.put(
            "/v1/principals/pm", json={"kind": "human", "display_name": "pm"}
        )
        client.post("/v1/projects", json={"id": "room", "name": "room"})
        join(client, "room", "agent")
        client.put(
            "/v1/principals/agent",
            json={"kind": "agent", "display_name": "agent"},
        )
        client.post("/v1/messages", json={
            "workspace_id": "room", "sender_id": "pm",
            "recipient_ids": [], "body": "남는 글",
        })
        client.delete("/v1/projects/room")

    with TestClient(create_app(database)) as client:
        assert not any(p["id"] == "room" for p in client.get("/v1/projects").json())
