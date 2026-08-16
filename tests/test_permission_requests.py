import json

from fastapi.testclient import TestClient

from dispatch_server.app import create_app


def test_permission_request_round_trip(tmp_path):
    with TestClient(create_app(tmp_path / "perm.db")) as client:
        created = client.post(
            "/v1/permission-requests",
            json={
                "workspace_id": "local",
                "session_id": "sess-1",
                "tool_name": "Write",
                "tool_input": json.dumps({"file_path": "/tmp/x", "content": "hi"}),
                "suggestions": json.dumps([{"type": "setMode", "mode": "acceptEdits"}]),
            },
        ).json()
        assert created["status"] == "pending"

        pending = client.get("/v1/workspaces/local/permission-requests").json()
        assert [item["id"] for item in pending] == [created["id"]]

        resolved = client.patch(
            f"/v1/permission-requests/{created['id']}", json={"status": "allowed"}
        ).json()
        assert resolved["status"] == "allowed"
        assert resolved["resolved_at"]

        assert client.get("/v1/workspaces/local/permission-requests").json() == []


def test_first_answer_wins(tmp_path):
    with TestClient(create_app(tmp_path / "perm.db")) as client:
        created = client.post(
            "/v1/permission-requests",
            json={
                "workspace_id": "local",
                "session_id": "sess-2",
                "tool_name": "Bash",
                "tool_input": json.dumps({"command": "rm -rf /"}),
                "suggestions": None,
            },
        ).json()

        client.patch(f"/v1/permission-requests/{created['id']}", json={"status": "denied"})
        # 사람이 누른 답과 시간 초과가 겹쳐도 먼저 온 쪽을 지킨다.
        again = client.patch(
            f"/v1/permission-requests/{created['id']}", json={"status": "expired"}
        ).json()
        assert again["status"] == "denied"


def test_unknown_request_is_not_found(tmp_path):
    with TestClient(create_app(tmp_path / "perm.db")) as client:
        assert client.get("/v1/permission-requests/nope").status_code == 404


def test_stale_pending_requests_stop_showing_as_cards(tmp_path, monkeypatch):
    """게이트가 죽으면 pending 행이 영원히 남는다.

    묻는 쪽은 정해진 시간만 기다리다 비켜선다. 그 뒤에도 pending인 것은 답을
    받아갈 프로세스가 없다는 뜻이라, PM 화면에 눌러도 아무 일 없는 카드가
    쌓인다. 8/16 실측에서 서버 재시작과 겹쳐 그대로 남았다.
    """
    from dispatch_server import db as db_module

    with TestClient(create_app(tmp_path / "perm.db")) as client:
        created = client.post(
            "/v1/permission-requests",
            json={
                "workspace_id": "local",
                "session_id": "sess-stale",
                "tool_name": "Bash",
                "tool_input": json.dumps({"command": "ls"}),
                "suggestions": None,
            },
        ).json()
        assert [item["id"] for item in client.get(
            "/v1/workspaces/local/permission-requests"
        ).json()] == [created["id"]]

        # 대기 한도를 지나면 카드에서 빠지고 만료로 남는다.
        monkeypatch.setattr(db_module, "PERMISSION_REQUEST_TTL_SECONDS", 0)
        assert client.get("/v1/workspaces/local/permission-requests").json() == []
        assert client.get(
            f"/v1/permission-requests/{created['id']}"
        ).json()["status"] == "expired"
