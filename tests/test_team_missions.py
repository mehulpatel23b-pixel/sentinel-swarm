"""End-to-end missions and error-recovery scenarios for the whole swarm."""

import asyncio

from sentinel_swarm import EventBus, MessageType, SentinelTeam
from sentinel_swarm.agents import AnalyzerAgent, ExecutorAgent, OrchestratorAgent, ReconAgent, ReporterAgent
from sentinel_swarm.base import BaseAgent
from sentinel_swarm.messages import Message
from sentinel_swarm.topics import Topics

AUTH_LOG = [
    "Oct 20 02:14:01 host sshd[101]: Failed password for root from 203.0.113.7 port 41822 ssh2",
    "Oct 20 02:14:03 host sshd[102]: Failed password for root from 203.0.113.7 port 41823 ssh2",
    "Oct 20 02:14:05 host sshd[103]: Failed password for root from 203.0.113.7 port 41824 ssh2",
    "Oct 20 02:14:07 host sshd[104]: invalid user admin from 203.0.113.7 port 41825 ssh2",
    "Oct 20 02:14:09 host sshd[105]: Failed password for root from 203.0.113.7 port 41826 ssh2",
    "Oct 20 02:14:11 host sshd[106]: Failed password for root from 203.0.113.7 port 41827 ssh2",
    "Oct 20 02:15:00 host CRON[110]: pam_unix(cron:session): session opened for user backup",
]


def test_full_mission_end_to_end():
    async def scenario():
        async with SentinelTeam() as team:
            result = await team.run(
                "Investigate the brute force attack in the auth logs",
                artifacts=AUTH_LOG,
                timeout=5.0,
            )
            return team, result

    team, result = asyncio.run(scenario())
    assert result["status"] == "completed"
    report = result["report"]
    assert report["mission_type"] == "security"
    assert report["findings"], "expected at least one finding"
    assert report["findings"][0]["severity"] == "high"
    assert any(a["type"] == "block_ip" and a["target"] == "203.0.113.7" for a in report["actions"])
    assert report["metrics"]["lines_scanned"] == 7
    assert report["metrics"]["failed_logins"] == 6
    assert "## Findings" in result["markdown"]
    assert all(agent.processed >= 1 for agent in team.agents)


def test_transient_agent_error_is_recovered_by_agent_level_retry():
    class FlakyReconAgent(ReconAgent):
        def __init__(self, name, bus, max_fails=1):
            super().__init__(name, bus)
            self.remaining_fails = max_fails

        async def handle(self, message):
            if self.remaining_fails > 0:
                self.remaining_fails -= 1
                raise RuntimeError("transient sensor glitch")
            await super().handle(message)

    async def scenario():
        bus = EventBus()
        agents = [
            OrchestratorAgent("orchestrator", bus, default_timeout=5.0),
            FlakyReconAgent("recon", bus),
            AnalyzerAgent("analyzer", bus),
            ExecutorAgent("executor", bus),
            ReporterAgent("reporter", bus),
        ]
        team = SentinelTeam(agents=agents)
        await team.start()
        try:
            return await team.run("Scan these auth logs for attacks", artifacts=AUTH_LOG, timeout=5.0)
        finally:
            await team.stop()

    result = asyncio.run(scenario())
    assert result["status"] == "completed"  # retry absorbed the failure
    assert result["report"]["findings"]


def test_persistent_agent_failure_fails_mission_gracefully():
    class BrokenReconAgent(BaseAgent):
        name = "recon"
        subscribes_to = (Topics.TASK_RECON,)

        async def handle(self, message):
            raise RuntimeError("sensor permanently offline")

    async def scenario():
        bus = EventBus()
        agents = [
            OrchestratorAgent("orchestrator", bus, default_timeout=10.0),
            BrokenReconAgent("recon", bus, max_retries=0),
            AnalyzerAgent("analyzer", bus),
            ExecutorAgent("executor", bus),
            ReporterAgent("reporter", bus),
        ]
        team = SentinelTeam(agents=agents)
        await team.start()
        try:
            return await team.run("Investigate the security breach", artifacts=AUTH_LOG, timeout=10.0)
        finally:
            await team.stop()

    result = asyncio.run(scenario())
    assert result["status"] == "failed"
    assert any("sensor permanently offline" in err for err in result["report"]["errors"])
    assert "failed" in result["markdown"].lower()


def test_mission_timeout_produces_failure_report():
    async def scenario():
        bus = EventBus()
        # no recon agent is ever started: results never arrive
        agents = [
            OrchestratorAgent("orchestrator", bus, default_timeout=10.0),
            AnalyzerAgent("analyzer", bus),
            ExecutorAgent("executor", bus),
            ReporterAgent("reporter", bus),
        ]
        team = SentinelTeam(agents=agents)
        await team.start()
        try:
            return await team.run("Investigate this incident", artifacts=AUTH_LOG, timeout=0.2)
        finally:
            await team.stop()

    result = asyncio.run(scenario())
    assert result["status"] == "failed"
    assert any("timed out" in err for err in result["report"]["errors"])


def test_concurrent_missions_stay_isolated():
    async def scenario():
        async with SentinelTeam() as team:
            first = asyncio.create_task(team.run("Investigate attack one", artifacts=AUTH_LOG, timeout=5.0))
            second = asyncio.create_task(team.run("Investigate attack two", artifacts=AUTH_LOG[:2], timeout=5.0))
            return await asyncio.gather(first, second)

    first, second = asyncio.run(scenario())
    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first["mission_id"] != second["mission_id"]
    assert first["report"]["metrics"]["failed_logins"] == 6
    assert second["report"]["metrics"]["failed_logins"] == 2


def test_agent_failure_publishes_error_envelope(bus):
    class ExplodingAgent(BaseAgent):
        name = "boom"
        subscribes_to = ("tasks.boom",)

        async def handle(self, message):
            raise ValueError("kaboom")

    async def scenario():
        errors = bus.subscribe(Topics.ERRORS)
        agent = ExplodingAgent("boom", bus, max_retries=0)
        task = asyncio.create_task(agent.start())
        await asyncio.sleep(0)
        bus.publish("tasks.boom", Message(type=MessageType.TASK, sender="test", topic="tasks.boom", payload={}))
        error = await asyncio.wait_for(errors.get(), timeout=1.0)
        agent.stop()
        await asyncio.wait_for(task, timeout=1.0)
        return agent, error

    agent, error = asyncio.run(scenario())
    assert error.type is MessageType.ERROR
    assert error.sender == "boom"
    assert "kaboom" in error.payload["error"]
    assert agent.failures == 1
