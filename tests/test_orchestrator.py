"""Orchestrator intent parsing."""

from sentinel_swarm.agents import OrchestratorAgent


def test_security_intent_recognised():
    intent = OrchestratorAgent.parse_intent("Investigate the ssh brute force attack in auth logs")
    assert intent["mission_type"] == "security"


def test_software_intent_recognised():
    intent = OrchestratorAgent.parse_intent("Find the bug and fix the failing test in the build pipeline")
    assert intent["mission_type"] == "software"


def test_default_intent_is_analysis():
    intent = OrchestratorAgent.parse_intent("Look at this")
    assert intent["mission_type"] == "analysis"
