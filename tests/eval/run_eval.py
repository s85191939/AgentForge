"""Evaluation runner for the AgentForge Finance agent.

Loads sample queries, runs them through the agent, and checks
whether the expected tools were called.

Usage:
    python tests/eval/run_eval.py

Requires a running Ghostfolio instance with seed data, and
OPENAI_API_KEY / GHOSTFOLIO_SECURITY_TOKEN set in .env.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from langchain_core.messages import ToolMessage

from agent.core.agent import create_agent

logger = logging.getLogger("agentforge.eval")

EVAL_DATA = Path(__file__).parent.parent.parent / "data" / "eval_datasets" / "sample_queries.json"


async def run_eval() -> list[dict]:
    """Execute all eval queries and return results."""
    agent = create_agent()

    with open(EVAL_DATA) as f:
        queries = json.load(f)

    results: list[dict] = []

    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        expected_tools = set(q["expected_tools"])

        logger.info(f"Running {qid}: {query_text}")
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": query_text}]},
                config={"configurable": {"thread_id": f"eval-{qid}"}},
            )

            messages = result.get("messages", [])

            # Collect all tools that were called
            tools_called: set[str] = set()
            for m in messages:
                if isinstance(m, ToolMessage):
                    tools_called.add(m.name)
                if hasattr(m, "tool_calls"):
                    for tc in m.tool_calls:
                        tools_called.add(tc["name"])

            # Check: expected tools (minus authenticate, which is now auto) are subset
            expected_adjusted = expected_tools - {"authenticate"}
            tool_match = expected_adjusted.issubset(tools_called)
            has_response = bool(messages and messages[-1].content)

            passed = tool_match and has_response
            results.append({
                "id": qid,
                "query": query_text,
                "tools_expected": sorted(expected_adjusted),
                "tools_called": sorted(tools_called),
                "tool_match": tool_match,
                "has_response": has_response,
                "pass": passed,
            })

            status = "PASS" if passed else "FAIL"
            logger.info(f"  {status} | expected: {sorted(expected_adjusted)} | "
                        f"called: {sorted(tools_called)}")

        except Exception as e:
            logger.error(f"  ERROR: {e}")
            results.append({
                "id": qid,
                "query": query_text,
                "pass": False,
                "error": str(e),
            })

    # Print summary
    passed_count = sum(1 for r in results if r.get("pass"))
    total = len(results)
    pct = (passed_count / total * 100) if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  Eval Results: {passed_count}/{total} passed ({pct:.0f}%)")
    print(f"{'=' * 60}")
    for r in results:
        status = "PASS" if r.get("pass") else "FAIL"
        error = f" — {r['error']}" if "error" in r else ""
        print(f"  [{status}] {r['id']}: {r.get('query', '')[:50]}{error}")
    print()

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_eval())
