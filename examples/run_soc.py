#!/usr/bin/env python3
"""Run the Sentinel Swarm against a log file and print the mission report.

Usage:
    python examples/run_soc.py [path/to/auth.log]
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sentinel_swarm import SentinelTeam  # noqa: E402

SAMPLE = """Oct 20 02:14:01 host sshd[101]: Failed password for root from 203.0.113.7 port 41822 ssh2
Oct 20 02:14:03 host sshd[102]: Failed password for root from 203.0.113.7 port 41823 ssh2
Oct 20 02:14:05 host sshd[103]: Failed password for root from 203.0.113.7 port 41824 ssh2
Oct 20 02:14:07 host sshd[104]: invalid user admin from 203.0.113.7 port 41825 ssh2
Oct 20 02:14:09 host sshd[105]: Failed password for root from 203.0.113.7 port 41826 ssh2
Oct 20 02:14:11 host sshd[106]: Failed password for root from 203.0.113.7 port 41827 ssh2
Oct 20 02:15:00 host CRON[110]: pam_unix(cron:session): session opened for user backup
Oct 20 02:16:00 host sshd[120]: Accepted publickey for deploy from 10.0.0.5 port 22 ssh2
"""


async def main() -> None:
    if len(sys.argv) > 1:
        artifacts = Path(sys.argv[1]).read_text().splitlines()
        source = sys.argv[1]
    else:
        artifacts = SAMPLE.splitlines()
        source = "built-in sample auth log"

    print(f"Launching Sentinel Swarm on {source} ({len(artifacts)} lines)...\n")
    async with SentinelTeam() as team:
        result = await team.run(
            "Investigate the brute force attack in the auth logs",
            artifacts=artifacts,
            timeout=30.0,
        )

    print(result["markdown"])
    print("\nAgent health:")
    for metric in team.metrics:
        print(f"  {metric['agent']:>12}  processed={metric['processed']} failures={metric['failures']}")

    print("\nJSON report written to report.json")
    Path("report.json").write_text(result["report"] and __import__("json").dumps(result["report"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
