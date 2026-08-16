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
