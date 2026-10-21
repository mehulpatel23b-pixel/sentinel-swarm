"""Event bus delivery semantics."""

from sentinel_swarm import EventBus, Message, MessageType
from tests.conftest import make_message


def test_subscribe_and_publish_delivers_message(bus: EventBus):
    queue = bus.subscribe("tasks.recon")
    message = make_message(payload={"hello": "world"})
    bus.publish("tasks.recon", message)
    assert queue.qsize() == 1
    assert queue.get_nowait() is message


def test_multiple_subscribers_each_receive_a_copy(bus: EventBus):
    first = bus.subscribe("tasks.recon")
    second = bus.subscribe("tasks.recon")
    bus.publish("tasks.recon", make_message())
    assert first.qsize() == 1
    assert second.qsize() == 1


def test_publish_to_topic_without_subscribers_is_a_noop(bus: EventBus):
    bus.publish("tasks.ghost", make_message())  # must not raise
    assert bus.subscriber_count("tasks.ghost") == 0


def test_unsubscribe_stops_delivery(bus: EventBus):
    queue = bus.subscribe("tasks.recon")
    bus.unsubscribe("tasks.recon", queue)
    bus.publish("tasks.recon", make_message())
    assert queue.qsize() == 0
    assert "tasks.recon" not in bus.topics()


def test_publish_stamps_the_topic_on_the_message(bus: EventBus):
    bus.subscribe("tasks.recon")
    message = make_message()
    message.topic = "stale.topic"
    bus.publish("tasks.recon", message)
    assert message.topic == "tasks.recon"


def test_async_publish_matches_sync_publish(bus: EventBus):
    import asyncio

    queue = bus.subscribe("tasks.recon")
    message = Message(type=MessageType.TASK, sender="t", topic="tasks.recon", payload={})

    async def scenario():
        await bus.publish_async("tasks.recon", message)

    asyncio.run(scenario())
    assert queue.get_nowait() is message
