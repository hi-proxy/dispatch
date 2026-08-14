from dispatch_server.db import DispatchDB


def setup_db(tmp_path):
    db = DispatchDB(tmp_path / "dispatch.db")
    pm = db.create_principal(kind="human", display_name="pm")
    agent = db.create_principal(kind="agent", display_name="agent1")
    return db, pm, agent


def test_incremental_messages_and_ack(tmp_path):
    db, pm, agent = setup_db(tmp_path)
    first, _ = db.send_message(
        workspace_id="poc",
        sender_id=pm["id"],
        recipient_ids=[agent["id"]],
        body="first",
    )
    second, _ = db.send_message(
        workspace_id="poc",
        sender_id=pm["id"],
        recipient_ids=[agent["id"]],
        body="second",
    )

    assert [message["body"] for message in db.messages_after(
        recipient_id=agent["id"], after=first["seq"]
    )] == ["second"]
    assert db.inbox_state(agent["id"]) == {
        "received_seq": 0,
        "processed_seq": 0,
        "pending_count": 2,
    }
    assert db.ack(
        recipient_id=agent["id"], through_seq=second["seq"], processed=False
    )["received_seq"] == second["seq"]
    state = db.ack(
        recipient_id=agent["id"], through_seq=second["seq"], processed=True
    )
    assert state == {
        "received_seq": second["seq"],
        "processed_seq": second["seq"],
        "pending_count": 0,
    }


def test_duplicate_recipient_is_idempotent(tmp_path):
    db, pm, agent = setup_db(tmp_path)
    message, events = db.send_message(
        workspace_id="poc",
        sender_id=pm["id"],
        recipient_ids=[agent["id"], agent["id"]],
        body="once",
    )
    assert message["recipient_ids"] == [agent["id"]]
    assert len(events) == 1
    assert db.inbox_state(agent["id"])["pending_count"] == 1


def test_events_replay_after_cursor(tmp_path):
    db, pm, agent = setup_db(tmp_path)
    _, first_events = db.send_message(
        workspace_id="poc",
        sender_id=pm["id"],
        recipient_ids=[agent["id"]],
        body="first",
    )
    _, second_events = db.send_message(
        workspace_id="poc",
        sender_id=pm["id"],
        recipient_ids=[agent["id"]],
        body="second",
    )
    replay = db.delivery_events_after(
        recipient_id=agent["id"], after=first_events[0]["event_seq"]
    )
    assert replay == second_events
