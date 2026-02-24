"""Evaluation runner for the AgentForge Finance agent.

Loads sample queries, runs them through the agent, and checks
whether the expected tools were called and response quality.

Usage:
    python tests/eval/run_eval.py
    python tests/eval/run_eval.py --category performance
    python tests/eval/run_eval.py --difficulty hard
    python tests/eval/run_eval.py --output results.json

Requires a running Ghostfolio instance with seed data, and
OPENAI_API_KEY / GHOSTFOLIO_SECURITY_TOKEN set in .env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from langchain_core.messages import ToolMessage

from agent.core.agent import create_agent

logger = logging.getLogger("agentforge.eval")

EVAL_DATA = Path(__file__).parent.parent.parent / "data" / "eval_datasets" / "sample_queries.json"


def check_response_keywords(response_text: str, expected_keywords: list[str]) -> bool:
    """Check if the response contains any of the expected keywords (case-insensitive)."""
    if not expected_keywords:
        return True
    lower_response = response_text.lower()
    return any(kw.lower() in lower_response for kw in expected_keywords)


async def run_eval(
    category: str | None = None,
    difficulty: str | None = None,
    output_path: str | None = None,
    delay: float = 2.0,
) -> list[dict]:
    """Execute eval queries and return results.

    Args:
        delay: Seconds to wait between queries to avoid rate limits (default 2s).
    """
    agent = create_agent()

    with open(EVAL_DATA) as f:
        queries = json.load(f)

    # Apply filters
    if category:
        queries = [q for q in queries if q["category"] == category]
    if difficulty:
        queries = [q for q in queries if q["difficulty"] == difficulty]

    if not queries:
        print("No queries match the specified filters.")
        return []

    results: list[dict] = []
    start_time = time.time()

    for i, q in enumerate(queries, 1):
        qid = q["id"]
        query_text = q["query"]
        expected_tools = set(q["expected_tools"])
        expected_keywords = q.get("expected_response_contains", [])

        print(f"  [{i}/{len(queries)}] {qid}: {query_text[:60]}...", end=" ", flush=True)
        query_start = time.time()

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
            response_text = messages[-1].content if has_response else ""
            keyword_match = check_response_keywords(response_text, expected_keywords)

            passed = tool_match and has_response
            query_time = time.time() - query_start

            results.append({
                "id": qid,
                "query": query_text,
                "category": q["category"],
                "difficulty": q["difficulty"],
                "tools_expected": sorted(expected_adjusted),
                "tools_called": sorted(tools_called),
                "tool_match": tool_match,
                "has_response": has_response,
                "keyword_match": keyword_match,
                "pass": passed,
                "latency_seconds": round(query_time, 2),
            })

            status = "PASS" if passed else "FAIL"
            kw_status = "KW:Y" if keyword_match else "KW:N"
            print(f"{status} ({kw_status}) [{query_time:.1f}s]")

        except Exception as e:
            query_time = time.time() - query_start
            logger.error(f"  ERROR: {e}")
            results.append({
                "id": qid,
                "query": query_text,
                "category": q["category"],
                "difficulty": q["difficulty"],
                "pass": False,
                "error": str(e),
                "latency_seconds": round(query_time, 2),
            })
            print(f"ERROR [{query_time:.1f}s]")

        # Throttle to avoid rate limits
        if delay > 0 and i < len(queries):
            await asyncio.sleep(delay)

    total_time = time.time() - start_time

    # Print summary
    passed_count = sum(1 for r in results if r.get("pass"))
    keyword_count = sum(1 for r in results if r.get("keyword_match"))
    total = len(results)
    pct = (passed_count / total * 100) if total > 0 else 0
    kw_pct = (keyword_count / total * 100) if total > 0 else 0

    sep = "=" * 64
    print(f"\n{sep}")
    print("  EVAL RESULTS")
    print(sep)
    print(f"  Tool Match:     {passed_count}/{total} passed ({pct:.0f}%)")
    print(f"  Keyword Match:  {keyword_count}/{total} passed ({kw_pct:.0f}%)")
    avg_t = total_time / total if total > 0 else 0
    print(f"  Total Time:     {total_time:.1f}s ({avg_t:.1f}s avg per query)")
    print(sep)

    # Category breakdown
    categories: dict[str, list[dict]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, []).append(r)

    cat_hdr = f"  {'Category':<25} {'Pass':>6} {'Total':>6} {'Rate':>6}"
    print(f"\n{cat_hdr}")
    dash_line = "  " + "-" * 45
    print(dash_line)
    for cat, cat_results in sorted(categories.items()):
        cat_passed = sum(1 for r in cat_results if r.get("pass"))
        cat_total = len(cat_results)
        cat_pct = (cat_passed / cat_total * 100) if cat_total > 0 else 0
        print(f"  {cat:<25} {cat_passed:>6} {cat_total:>6} {cat_pct:>5.0f}%")

    # Difficulty breakdown
    diff_hdr = f"  {'Difficulty':<25} {'Pass':>6} {'Total':>6} {'Rate':>6}"
    print(f"\n{diff_hdr}")
    print(dash_line)
    for diff in ["easy", "medium", "hard"]:
        diff_results = [r for r in results if r.get("difficulty") == diff]
        if diff_results:
            diff_passed = sum(1 for r in diff_results if r.get("pass"))
            diff_total = len(diff_results)
            diff_pct = (diff_passed / diff_total * 100) if diff_total > 0 else 0
            print(f"  {diff:<25} {diff_passed:>6} {diff_total:>6} {diff_pct:>5.0f}%")

    # Failed queries
    failed = [r for r in results if not r.get("pass")]
    if failed:
        print("\n  FAILED QUERIES:")
        for r in failed:
            error = f" -- {r['error']}" if "error" in r else ""
            print(f"  [{r['id']}] {r.get('query', '')[:55]}{error}")

    print()

    # Write results to file if requested
    if output_path:
        output = {
            "summary": {
                "total": total,
                "passed": passed_count,
                "pass_rate": round(pct, 1),
                "keyword_match_rate": round(kw_pct, 1),
                "total_time_seconds": round(total_time, 1),
                "avg_latency_seconds": round(total_time / total, 1) if total > 0 else 0,
            },
            "results": results,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"  Results written to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AgentForge eval suite")
    parser.add_argument("--category", help="Filter by category (e.g. performance, portfolio_read)")
    parser.add_argument(
        "--difficulty", choices=["easy", "medium", "hard"],
        help="Filter by difficulty",
    )
    parser.add_argument("--output", help="Write JSON results to file")
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds between queries to avoid rate limits (default 2.0, 0 to disable)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_eval(
        category=args.category,
        difficulty=args.difficulty,
        output_path=args.output,
        delay=args.delay,
    ))
