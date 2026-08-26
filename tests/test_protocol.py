"""Agent 通信协议（AgentMessage / MessageBus）单元测试。"""

from app.agents.protocol import BROADCAST, AgentMessage, MessageBus, MessageType


def test_agent_message_to_dict():
    msg = AgentMessage(
        sender="coordinator",
        receiver="memory",
        message_type=MessageType.REQUEST,
        payload={"user_id": "u1"},
    )
    data = msg.to_dict()
    assert data["sender"] == "coordinator"
    assert data["receiver"] == "memory"
    assert data["message_type"] == MessageType.REQUEST
    assert data["payload"] == {"user_id": "u1"}
    assert data["message_id"]
    assert data["timestamp"]


def test_publish_delivers_to_matching_receiver():
    bus = MessageBus()
    received = []

    def handler(message):
        received.append(message)

    bus.subscribe("memory", handler)
    bus.publish(
        AgentMessage("coordinator", "memory", MessageType.REQUEST, {"key": "v"})
    )
    assert len(received) == 1
    assert received[0].sender == "coordinator"


def test_publish_does_not_deliver_to_other_agents():
    bus = MessageBus()
    received = []

    def handler(message):
        received.append(message)

    bus.subscribe("other_agent", handler)
    bus.publish(
        AgentMessage("coordinator", "memory", MessageType.REQUEST, {})
    )
    assert received == []


def test_broadcast_delivers_to_all():
    bus = MessageBus()
    received = []
    bus.subscribe(BROADCAST, received.append)
    bus.subscribe("memory", received.append)
    bus.publish(AgentMessage("a", "memory", MessageType.EVENT, {}))
    # 广播订阅者收到，且精确匹配 receiver 的 memory 订阅者也收到
    assert len(received) == 2


def test_handler_exception_does_not_break_bus():
    bus = MessageBus()

    def bad_handler(message):
        raise RuntimeError("boom")

    good = []

    def good_handler(message):
        good.append(message)

    bus.subscribe(BROADCAST, bad_handler)
    bus.subscribe(BROADCAST, good_handler)
    bus.publish(AgentMessage("a", "b", MessageType.EVENT, {}))
    assert len(good) == 1


def test_history_records_published_messages():
    bus = MessageBus()
    bus.publish(AgentMessage("a", "b", MessageType.EVENT, {"n": 1}))
    bus.publish(AgentMessage("c", "d", MessageType.RESPONSE, {"n": 2}))
    assert len(bus.history()) == 2


def test_clear_resets_bus():
    bus = MessageBus()
    bus.publish(AgentMessage("a", "b", MessageType.EVENT, {}))
    bus.clear()
    assert bus.history() == []
