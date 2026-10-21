"""Message envelope semantics."""

from sentinel_swarm import Message, MessageType


def test_message_serialization_round_trip():
    message = Message(
        type=MessageType.TASK,
        sender="orchestrator",
        topic="tasks.recon",
        payload={"artifacts": ["line"]},
    )
    restored = Message.from_dict(message.to_dict())
    assert restored.type is MessageType.TASK
    assert restored.sender == "orchestrator"
    assert restored.topic == "tasks.recon"
    assert restored.payload == {"artifacts": ["line"]}
    assert restored.correlation_id == message.correlation_id


def test_correlation_ids_are_unique_per_message():
    first = Message(type=MessageType.RESULT, sender="a", topic="t")
    second = Message(type=MessageType.RESULT, sender="a", topic="t")
    assert first.correlation_id != second.correlation_id


def test_task_factory_sets_correct_type():
    message = Message.task("user", "missions.new", {"description": "x"}, "abc123")
    assert message.type is MessageType.TASK
    assert message.correlation_id == "abc123"
