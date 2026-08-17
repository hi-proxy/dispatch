from fungis_node.pm_tui import PMController


class FakePMClient:
    pm_id = "pm-local"

    def __init__(self):
        self.sent = []

    def send(self, recipient_id, body, *, in_reply_to=None):
        self.sent.append((recipient_id, body, in_reply_to))

    def timeline(self):
        return []

    def attention(self):
        return []

    def agent_statuses(self):
        return []

    def shared(self):
        return []

    def work_items(self):
        return []

    def put_shared(self, key, value):
        pass

    def delete_shared(self, key):
        pass


def test_answer_attention_links_reply_and_removes_request():
    client = FakePMClient()
    controller = PMController(client)
    controller.attention = [
        {
            "seq": 9,
            "sender_id": "agent-1",
            "sender_name": "agent-1",
            "reply_level": "r3",
            "body": "approve?",
        }
    ]
    controller.targets = [{"local_name": "agent-1"}]
    controller.answer_attention("approved")
    assert client.sent == [("agent-1", "approved", 9)]
    assert controller.attention == []


def test_attention_selection_wraps():
    controller = PMController(FakePMClient())
    controller.attention = [{"seq": 1}, {"seq": 2}]
    controller.move_attention(-1)
    assert controller.attention_selected == 1
    controller.move_attention(1)
    assert controller.attention_selected == 0


def test_shared_selection_wraps_and_delete_refreshes():
    controller = PMController(FakePMClient())
    controller.shared_values = [{"key": "a"}, {"key": "b"}]
    controller.move_shared(-1)
    assert controller.shared_selected == 1
    controller.delete_selected_shared()
    assert controller.shared_values == []
