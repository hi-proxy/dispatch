from fastapi.testclient import TestClient

from dispatch_server.app import create_app


def test_message_flow(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        pm = client.post(
            "/v1/principals", json={"kind": "human", "display_name": "pm"}
        ).json()
        agent = client.post(
            "/v1/principals", json={"kind": "agent", "display_name": "agent1"}
        ).json()
        with client.websocket_connect(f"/v1/events/{agent['id']}?after=0") as websocket:
            message = client.post(
                "/v1/messages",
                json={
                    "workspace_id": "poc",
                    "sender_id": pm["id"],
                    "recipient_ids": [agent["id"]],
                    "body": "hello",
                },
            ).json()
            event = websocket.receive_json()
            assert event["kind"] == "inbox_available"
            assert event["through_seq"] == message["seq"]

        messages = client.get(
            "/v1/messages", params={"recipient": agent["id"], "after": 0}
        ).json()
        assert [item["body"] for item in messages] == ["hello"]
        state = client.post(
            "/v1/inbox/ack-processed",
            json={"recipient_id": agent["id"], "through_seq": message["seq"]},
        ).json()
        assert state["pending_count"] == 0


def test_project_message_bookmarks_are_ordered_and_deletable(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        messages = [
            client.post(
                "/v1/messages",
                json={
                    "workspace_id": "local", "sender_id": "pm",
                    "recipient_ids": ["agent"], "body": body,
                },
            ).json()
            for body in ("wave one", "wave two")
        ]
        later = client.post(
            f"/v1/workspaces/local/messages/{messages[1]['seq']}/bookmarks",
            json={"label": "디자인 웨이브2 완료", "created_by": "pm"},
        ).json()
        client.post(
            f"/v1/workspaces/local/messages/{messages[0]['seq']}/bookmarks",
            json={"label": "디자인 웨이브1 완료", "created_by": "pm"},
        )

        bookmarks = client.get("/v1/workspaces/local/bookmarks").json()
        assert [item["message_seq"] for item in bookmarks] == [
            messages[0]["seq"], messages[1]["seq"]
        ]
        assert bookmarks[0]["created_by_name"] == "pm"
        assert client.delete(
            f"/v1/workspaces/local/bookmarks/{later['id']}"
        ).status_code == 204
        assert [item["label"] for item in client.get(
            "/v1/workspaces/local/bookmarks"
        ).json()] == ["디자인 웨이브1 완료"]


def test_timeline_pins_mark_message_gaps_separately_from_bookmarks(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        messages = [
            client.post(
                "/v1/messages",
                json={
                    "workspace_id": "local", "sender_id": "pm",
                    "recipient_ids": ["agent"], "body": f"message-{index}",
                },
            ).json()
            for index in range(3)
        ]
        second = client.post(
            f"/v1/workspaces/local/messages/{messages[1]['seq']}/timeline-pins",
            json={"label": "디자인 웨이브2 완료", "created_by": "pm"},
        ).json()
        client.post(
            f"/v1/workspaces/local/messages/{messages[0]['seq']}/timeline-pins",
            json={"label": "디자인 웨이브1 완료", "created_by": "pm"},
        )

        pins = client.get("/v1/workspaces/local/timeline-pins").json()
        assert [pin["after_message_seq"] for pin in pins] == [
            messages[0]["seq"], messages[1]["seq"]
        ]
        assert client.post(
            f"/v1/workspaces/local/messages/{messages[1]['seq']}/timeline-pins",
            json={"label": "duplicate gap", "created_by": "pm"},
        ).status_code == 409
        assert client.delete(
            f"/v1/workspaces/local/timeline-pins/{second['id']}"
        ).status_code == 204
        assert [pin["label"] for pin in client.get(
            "/v1/workspaces/local/timeline-pins"
        ).json()] == ["디자인 웨이브1 완료"]


def test_idempotent_principal_sync_and_pm_timeline_status(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for _ in range(2):
            assert client.put(
                "/v1/principals/pm-local",
                json={"id": "pm-local", "kind": "human", "display_name": "PM"},
            ).status_code == 200
            assert client.put(
                "/v1/principals/agent-1",
                json={"id": "agent-1", "kind": "agent", "display_name": "agent-1"},
            ).status_code == 200
        message = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "pm-local",
                "recipient_ids": ["agent-1"],
                "body": "check status",
            },
        ).json()
        before = client.get("/v1/timeline/pm-local").json()
        assert before[0]["body"] == "check status"
        assert before[0]["recipients"][0]["processed_at"] is None
        client.post(
            "/v1/inbox/ack-processed",
            json={"recipient_id": "agent-1", "through_seq": message["seq"]},
        )
        after = client.get("/v1/timeline/pm-local").json()
        assert after[0]["recipients"][0]["processed_at"] is not None


def test_pm_attention_is_prioritized_and_resolved_by_linked_reply(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        low = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "agent",
                "recipient_ids": ["pm"],
                "body": "review later",
                "kind": "pm_request",
                "reply_level": "r2",
            },
        ).json()
        urgent = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "agent",
                "recipient_ids": ["pm"],
                "body": "approve destructive step",
                "kind": "pm_request",
                "reply_level": "r3",
            },
        ).json()
        attention = client.get("/v1/attention/pm").json()
        assert [item["seq"] for item in attention] == [urgent["seq"], low["seq"]]
        client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "pm",
                "recipient_ids": ["agent"],
                "body": "approved",
                "in_reply_to": urgent["seq"],
            },
        )
        assert [item["seq"] for item in client.get("/v1/attention/pm").json()] == [
            low["seq"]
        ]


def test_message_context_is_indexed_and_inherited_by_replies(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        parent = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "pm",
                "recipient_ids": ["agent"],
                "body": "work on this branch",
                "track": "branch/feature-a",
                "tags": ["ticket/ARC-42", "review", "review"],
            },
        ).json()
        assert parent["track"] == "branch/feature-a"
        assert parent["tags"] == ["ticket/ARC-42", "review"]

        inherited = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "agent",
                "recipient_ids": ["pm"],
                "body": "done",
                "in_reply_to": parent["seq"],
            },
        ).json()
        assert inherited["track"] == parent["track"]
        assert inherited["tags"] == parent["tags"]

        detached = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "agent",
                "recipient_ids": ["pm"],
                "body": "separate note",
                "in_reply_to": parent["seq"],
                "inherit_context": False,
            },
        ).json()
        assert detached["track"] is None
        assert detached["tags"] == []

        timeline = client.get("/v1/workspaces/local/timeline").json()
        assert timeline[0]["tags"] == ["ticket/ARC-42", "review"]
        assert timeline[1]["track"] == "branch/feature-a"


def test_shared_values_are_versioned_selectable_and_deletable(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        client.put(
            "/v1/principals/pm",
            json={"id": "pm", "kind": "human", "display_name": "pm"},
        )
        first = client.put(
            "/v1/shared/local/repository",
            params={"updated_by": "pm"},
            json={"value": "https://example.test/repo"},
        ).json()
        assert first["version"] == 1
        second = client.put(
            "/v1/shared/local/repository",
            params={"updated_by": "pm"},
            json={"value": "ssh://git@example.test/repo"},
        ).json()
        assert second["version"] == 2
        client.put(
            "/v1/shared/local/review-rule",
            params={"updated_by": "pm"},
            json={"value": "r3 before deletion"},
        )
        selected = client.get(
            "/v1/shared/local", params=[("keys", "review-rule")]
        ).json()
        assert [(item["key"], item["value"]) for item in selected] == [
            ("review-rule", "r3 before deletion")
        ]
        assert client.delete("/v1/shared/local/repository").status_code == 204
        assert [item["key"] for item in client.get("/v1/shared/local").json()] == [
            "review-rule"
        ]


def test_work_start_report_done_tracks_elapsed_without_fake_tokens(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        client.put(
            "/v1/principals/agent",
            json={"id": "agent", "kind": "agent", "display_name": "agent"},
        )
        started = client.post(
            "/v1/work",
            json={"workspace_id": "local", "agent_id": "agent", "title": "build"},
        ).json()
        assert started["status"] == "active"
        assert started["token_usage"] is None
        duplicate = client.post(
            "/v1/work",
            json={"workspace_id": "local", "agent_id": "agent", "title": "other"},
        )
        assert duplicate.status_code == 409
        reported = client.post(
            "/v1/work/agent/report", json={"report": "halfway"}
        ).json()
        assert reported["last_report"] == "halfway"
        done = client.post(
            "/v1/work/agent/done", json={"report": "verified"}
        ).json()
        assert done["status"] == "done"
        assert done["ended_at"] is not None
        assert done["elapsed_seconds"] >= 0
        listed = client.get("/v1/work/local").json()
        assert [(item["title"], item["last_report"]) for item in listed] == [
            ("build", "verified")
        ]


def test_two_pms_share_workspace_timeline_and_either_can_resolve_attention(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (
            ("pm-a", "human"), ("pm-b", "human"), ("agent-a", "agent")
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        client.post(
            "/v1/messages",
            json={
                "workspace_id": "shared-room",
                "sender_id": "pm-a",
                "recipient_ids": ["agent-a"],
                "body": "from first PM",
            },
        )
        request = client.post(
            "/v1/messages",
            json={
                "workspace_id": "shared-room",
                "sender_id": "agent-a",
                "recipient_ids": ["pm-a"],
                "body": "need approval",
                "kind": "pm_request",
                "reply_level": "r3",
            },
        ).json()
        timeline = client.get(
            "/v1/workspaces/shared-room/timeline"
        ).json()
        assert [item["body"] for item in timeline] == [
            "from first PM", "need approval"
        ]
        assert client.get(
            "/v1/workspaces/shared-room/attention"
        ).json()[0]["seq"] == request["seq"]
        client.post(
            "/v1/messages",
            json={
                "workspace_id": "shared-room",
                "sender_id": "pm-b",
                "recipient_ids": ["agent-a"],
                "body": "approved by second PM",
                "in_reply_to": request["seq"],
            },
        )
        assert client.get(
            "/v1/workspaces/shared-room/attention"
        ).json() == []


def test_multiple_recipients_and_pm_reference_are_distinct(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (
            ("pm", "human"), ("agent-a", "agent"), ("agent-b", "agent")
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        message = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "agent-a",
                "recipient_ids": ["agent-a", "agent-b", "agent-b"],
                "reference_ids": ["pm", "agent-b"],
                "body": "coordinate",
            },
        ).json()
        assert message["recipient_ids"] == ["agent-a", "agent-b"]
        assert message["reference_ids"] == ["pm"]
        timeline = client.get("/v1/workspaces/local/timeline").json()
        assert [item["recipient_id"] for item in timeline[0]["recipients"]] == [
            "agent-a", "agent-b"
        ]
        assert timeline[0]["references"] == [
            {"principal_id": "pm", "display_name": "pm"}
        ]


def test_reference_is_delivered_but_marked_as_listen_only(tmp_path):
    """참조도 받아 봐야 맥락이 되지만, 수신자 자리에 서면 안 된다.

    배달하지 않으면 보내는 쪽이 참조 대신 수신자로 넣게 되고, 받는 쪽은
    그것을 지시로 읽어 서로 답장을 물고 늘어진다.
    """
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (
            ("pm", "human"), ("manager", "agent"), ("builder", "agent")
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        client.post(
            "/v1/messages",
            json={
                "workspace_id": "local",
                "sender_id": "manager",
                "recipient_ids": ["pm"],
                "reference_ids": ["builder"],
                "body": "보고",
            },
        )
        delivered = client.get(
            "/v1/messages", params={"recipient": "builder", "after": 0}
        ).json()
        assert [item["body"] for item in delivered] == ["보고"]
        assert delivered[0]["is_reference"] == 1

        to_pm = client.get(
            "/v1/messages", params={"recipient": "pm", "after": 0}
        ).json()
        assert to_pm[0]["is_reference"] == 0

        timeline = client.get("/v1/workspaces/local/timeline").json()
        assert [item["recipient_id"] for item in timeline[0]["recipients"]] == ["pm"]


def test_agent_chain_counts_only_since_the_last_human_message(tmp_path):
    """길어진 것을 알려만 준다. 막지는 않는다."""
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (
            ("pm", "human"), ("a", "agent"), ("b", "agent")
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )

        def post(sender: str, recipients: list[str], body: str) -> None:
            client.post(
                "/v1/messages",
                json={
                    "workspace_id": "local", "sender_id": sender,
                    "recipient_ids": recipients, "body": body,
                },
            )

        post("pm", ["a", "b"], "둘 다 본다")
        post("a", ["pm", "b"], "1")
        post("b", ["pm", "a"], "2")
        post("a", ["pm", "b"], "3")
        chains = {
            item["body"]: item["agent_chain"]
            for item in client.get(
                "/v1/messages", params={"recipient": "b", "after": 0}
            ).json()
        }
        assert chains == {"둘 다 본다": 0, "1": 1, "3": 3}

        # 사람이 다시 말하면 0부터 센다.
        post("pm", ["a", "b"], "정리하자")
        post("b", ["pm", "a"], "4")
        after = {
            item["body"]: item["agent_chain"]
            for item in client.get(
                "/v1/messages", params={"recipient": "a", "after": 0}
            ).json()
        }
        assert after["정리하자"] == 0
        assert after["4"] == 1


def test_role_address_queues_until_assignment_and_preserves_history(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (
            ("pm", "human"), ("agent-a", "agent"), ("agent-b", "agent")
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        role = client.post(
            "/v1/workspaces/local/roles",
            json={"name": "front1", "onboarding_prompt": "You own front1."},
        ).json()
        queued = client.post(
            "/v1/messages",
            json={
                "workspace_id": "local", "sender_id": "pm",
                "role_ids": [role["id"]], "body": "queued task",
            },
        ).json()
        assert queued["recipient_ids"] == []
        assert client.get("/v1/messages", params={"recipient": "agent-a", "after": 0}).json() == []
        assert client.delete(f"/v1/roles/{role['id']}").status_code == 409

        assigned = client.put(
            f"/v1/roles/{role['id']}/assignment",
            json={
                "agent_id": "agent-a", "assigned_by": "pm",
                "send_onboarding": True,
            },
        ).json()
        assert assigned["agent_id"] == "agent-a"
        delivered = client.get(
            "/v1/messages", params={"recipient": "agent-a", "after": 0}
        ).json()
        assert [item["body"] for item in delivered] == ["queued task", "You own front1."]
        assert delivered[0]["role_recipients"][0]["name"] == "front1"

        client.delete(f"/v1/roles/{role['id']}/assignment")
        client.put(
            f"/v1/roles/{role['id']}/assignment",
            json={"agent_id": "agent-b", "assigned_by": "pm"},
        )
        history = client.get(f"/v1/roles/{role['id']}/assignments").json()
        assert [item["agent_id"] for item in history] == ["agent-b", "agent-a"]
        assert history[0]["ended_at"] is None
        assert history[1]["ended_at"] is not None
        assert client.get(
            "/v1/messages", params={"recipient": "agent-b", "after": 0}
        ).json() == []
        assert client.delete(f"/v1/roles/{role['id']}").status_code == 204
        recreated = client.post(
            "/v1/workspaces/local/roles", json={"name": "front1"}
        )
        assert recreated.status_code == 201


def test_role_avatar_is_stored_separately_from_role_json(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        role = client.post(
            "/v1/workspaces/local/roles", json={"name": "design-lead"}
        ).json()
        assert role["has_avatar"] is False
        image = b"\x89PNG\r\n\x1a\nminimal-test-image"
        uploaded = client.put(
            f"/v1/roles/{role['id']}/avatar",
            content=image,
            headers={"content-type": "image/png"},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["has_avatar"] is True
        assert "avatar" not in uploaded.json()
        fetched = client.get(f"/v1/roles/{role['id']}/avatar")
        assert fetched.content == image
        assert fetched.headers["content-type"] == "image/png"
        client.delete(f"/v1/roles/{role['id']}/avatar")
        assert client.get(f"/v1/roles/{role['id']}/avatar").status_code == 404


def test_projects_allow_same_agent_one_role_per_project(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        second = client.post("/v1/projects", json={"name": "Second"}).json()
        local_role = client.post(
            "/v1/workspaces/local/roles", json={"name": "devlead"}
        ).json()
        second_role = client.post(
            f"/v1/workspaces/{second['id']}/roles", json={"name": "reviewer"}
        ).json()
        for role in (local_role, second_role):
            response = client.put(
                f"/v1/roles/{role['id']}/assignment",
                json={"agent_id": "agent", "assigned_by": "pm"},
            )
            assert response.status_code == 200
        memberships = client.get("/v1/agent-role-memberships").json()
        assert {(item["project_name"], item["role_name"]) for item in memberships} == {
            ("Local", "devlead"), ("Second", "reviewer")
        }


def test_pm_profile_and_avatar_are_global(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        client.put(
            "/v1/principals/pm",
            json={"id": "pm", "kind": "human", "display_name": "PM"},
        )
        updated = client.patch(
            "/v1/pm-profiles/pm", json={"display_name": "Product Lead"}
        ).json()
        assert updated["display_name"] == "Product Lead"
        client.put(
            "/v1/principals/pm",
            json={"id": "pm", "kind": "human", "display_name": "PM"},
        )
        assert client.get("/v1/pm-profiles/pm").json()["display_name"] == "Product Lead"
        image = b"\x89PNG\r\n\x1a\npm-profile"
        assert client.put(
            "/v1/pm-profiles/pm/avatar", content=image,
            headers={"content-type": "image/png"},
        ).status_code == 200
        assert client.get("/v1/pm-profiles/pm").json()["has_avatar"] is True
        assert client.get("/v1/pm-profiles/pm/avatar").content == image


def test_project_bootstrap_returns_agent_specific_role_directory(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind, name in (
            ("pm", "human", "Product Lead"),
            ("agent-a", "agent", "Alice Session"),
            ("agent-b", "agent", "Bob Session"),
        ):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": name},
            )
        lead = client.post(
            "/v1/workspaces/local/roles", json={"name": "dev-lead"}
        ).json()
        client.post("/v1/workspaces/local/roles", json={"name": "reviewer"})
        client.put(
            f"/v1/roles/{lead['id']}/assignment",
            json={"agent_id": "agent-a", "assigned_by": "pm"},
        )
        bootstrap = client.get(
            "/v1/projects/local/bootstrap",
            params={"agent_id": "agent-a", "pm_id": "pm"},
        ).json()
        assert bootstrap["project"]["name"] == "Local"
        assert bootstrap["own_role"]["name"] == "dev-lead"
        assert bootstrap["roles"][0]["self"] is True
        assert bootstrap["roles"][1]["assigned"] is False
        assert bootstrap["usage"]["reply_pm"] == 'dispatch reply "..."'
        assert bootstrap["usage"]["history"] == "dispatch history 20"
        assert "dispatch history 20" in bootstrap["usage"]["recovery"]
        assert len(bootstrap["revision"]) == 12


def test_project_history_supports_compaction_restore_after_sequence(tmp_path):
    app = create_app(tmp_path / "api.db")
    with TestClient(app) as client:
        for principal_id, kind in (("pm", "human"), ("agent", "agent")):
            client.put(
                f"/v1/principals/{principal_id}",
                json={"id": principal_id, "kind": kind, "display_name": principal_id},
            )
        sequences = []
        for body, sender, recipient in (
            ("first", "pm", "agent"),
            ("second", "agent", "pm"),
            ("third", "pm", "agent"),
        ):
            sequences.append(client.post(
                "/v1/messages",
                json={
                    "workspace_id": "local", "sender_id": sender,
                    "recipient_ids": [recipient], "body": body,
                },
            ).json()["seq"])
        latest = client.get(
            "/v1/workspaces/local/timeline", params={"limit": 2}
        ).json()
        assert [item["body"] for item in latest] == ["second", "third"]
        after = client.get(
            "/v1/workspaces/local/timeline",
            params={"limit": 20, "after": sequences[0]},
        ).json()
        assert [item["body"] for item in after] == ["second", "third"]
        before = client.get(
            "/v1/workspaces/local/timeline",
            params={"limit": 2, "before": sequences[-1]},
        ).json()
        assert [item["body"] for item in before] == ["first", "second"]
        assert client.get(
            "/v1/workspaces/local/timeline",
            params={"after": sequences[0], "before": sequences[-1]},
        ).status_code == 422
        assert client.post(
            "/v1/messages",
            json={
                "workspace_id": "local", "sender_id": "pm",
                "recipient_ids": ["agent"], "body": "x" * 20001,
            },
        ).status_code == 422
