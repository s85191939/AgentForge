"""Evaluation runner for the AgentForge Finance agent.

Implements a multi-stage eval framework:
  Stage 1 — Golden Sets: binary checks (tool match, keyword match, negative validation)
  Stage 2 — Labeled Scenarios: subcategory tags + coverage matrix
  Stage 5 — Experiments: variant tracking with latency & cost

Usage:
    python tests/eval/run_eval.py
    python tests/eval/run_eval.py --category performance
    python tests/eval/run_eval.py --difficulty hard
    python tests/eval/run_eval.py --output results.json
    python tests/eval/run_eval.py --variant new_prompt

Requires a running Ghostfolio instance with seed data, and
OPENAI_API_KEY / GHOSTFOLIO_SECURITY_TOKEN set in .env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from langchain_core.messages import ToolMessage

from agent.core.agent import create_agent

logger = logging.getLogger("agentforge.eval")

EVAL_DATA = Path(__file__).parent.parent.parent / "data" / "eval_datasets" / "sample_queries.json"

# ─── Cost estimation (per 1K tokens, approximate) ───────────────────────────
MODEL_COSTS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "openai/gpt-4o": {"input": 0.0025, "output": 0.01},
}
DEFAULT_COST = {"input": 0.003, "output": 0.012}

# Rough token estimate: 1 token ≈ 4 chars
CHARS_PER_TOKEN = 4


def estimate_cost(query: str, response: str, model: str = "gpt-4o") -> float:
    """Rough cost estimate for a single query-response pair."""
    costs = MODEL_COSTS.get(model, DEFAULT_COST)
    input_tokens = len(query) / CHARS_PER_TOKEN / 1000
    output_tokens = len(response) / CHARS_PER_TOKEN / 1000
    return round(input_tokens * costs["input"] + output_tokens * costs["output"], 6)


# ─── Stage 1: Binary Checks ─────────────────────────────────────────────────


def check_keywords(response_text: str, expected: list[str]) -> bool:
    """Check if the response contains ANY of the expected keywords (case-insensitive)."""
    if not expected:
        return True
    lower = response_text.lower()
    return any(kw.lower() in lower for kw in expected)


def check_exclusions(response_text: str, excluded: list[str]) -> bool:
    """Check that response does NOT contain any excluded phrases (negative validation).

    Returns True if NONE of the excluded phrases appear in the response.
    """
    if not excluded:
        return True
    lower = response_text.lower()
    return all(phrase.lower() not in lower for phrase in excluded)


# ─── Stage 2: Coverage Matrix ────────────────────────────────────────────────


def print_coverage_matrix(results: list[dict]) -> None:
    """Print a subcategory x difficulty coverage matrix."""
    # Build grid: subcategory -> difficulty -> (pass, total)
    grid: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    for r in results:
        sub = r.get("subcategory", "unknown")
        diff = r.get("difficulty", "unknown")
        grid[sub][diff][1] += 1
        if r.get("pass"):
            grid[sub][diff][0] += 1

    difficulties = ["easy", "medium", "hard"]
    header = f"  {'Subcategory':<28}"
    for d in difficulties:
        header += f" | {d:>8}"
    print(f"\n{header}")
    print("  " + "-" * (28 + 3 * 11))

    for sub in sorted(grid.keys()):
        row = f"  {sub:<28}"
        for d in difficulties:
            p, t = grid[sub][d]
            if t > 0:
                row += f" | {p}/{t:>5}"
            else:
                row += f" | {'--':>8}"
        print(row)


# ─── Main Eval Runner ────────────────────────────────────────────────────────


async def run_eval(
    category: str | None = None,
    difficulty: str | None = None,
    output_path: str | None = None,
    delay: float = 2.0,
    variant: str = "baseline",
) -> list[dict]:
    """Execute eval queries and return results.

    Args:
        category: Filter by category.
        difficulty: Filter by difficulty.
        output_path: Write JSON results to this path.
        delay: Seconds to wait between queries to avoid rate limits.
        variant: Experiment variant name for A/B tracking.
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
    total_cost = 0.0

    print(f"\n  Variant: {variant}")
    print(f"  Queries: {len(queries)}")
    print()

    for i, q in enumerate(queries, 1):
        qid = q["id"]
        query_text = q["query"]
        expected_tools = set(q["expected_tools"])
        expected_keywords = q.get("expected_response_contains", [])
        excluded_phrases = q.get("expected_response_excludes", [])
        subcategory = q.get("subcategory", "unknown")

        print(
            f"  [{i}/{len(queries)}] {qid}: {query_text[:60]}...",
            end=" ", flush=True,
        )
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

            # ── Stage 1: Binary Checks ──
            expected_adjusted = expected_tools - {"authenticate"}
            tool_match = expected_adjusted.issubset(tools_called)
            has_response = bool(messages and messages[-1].content)
            response_text = messages[-1].content if has_response else ""
            keyword_match = check_keywords(response_text, expected_keywords)
            exclusion_pass = check_exclusions(response_text, excluded_phrases)

            passed = tool_match and has_response
            query_time = time.time() - query_start
            cost = estimate_cost(query_text, response_text)
            total_cost += cost

            entry = {
                "id": qid,
                "query": query_text,
                "category": q["category"],
                "subcategory": subcategory,
                "difficulty": q["difficulty"],
                "variant": variant,
                "tools_expected": sorted(expected_adjusted),
                "tools_called": sorted(tools_called),
                "tool_match": tool_match,
                "has_response": has_response,
                "keyword_match": keyword_match,
                "exclusion_pass": exclusion_pass,
                "pass": passed,
                "latency_seconds": round(query_time, 2),
                "estimated_cost": cost,
            }

            results.append(entry)

            # Console output
            status = "PASS" if passed else "FAIL"
            kw_tag = "KW:Y" if keyword_match else "KW:N"
            ex_tag = "EX:Y" if exclusion_pass else "EX:N"
            print(f"{status} ({kw_tag} {ex_tag}) [{query_time:.1f}s]")

        except Exception as e:
            query_time = time.time() - query_start
            logger.error(f"  ERROR: {e}")
            results.append({
                "id": qid,
                "query": query_text,
                "category": q["category"],
                "subcategory": subcategory,
                "difficulty": q["difficulty"],
                "variant": variant,
                "pass": False,
                "error": str(e),
                "latency_seconds": round(query_time, 2),
            })
            print(f"ERROR [{query_time:.1f}s]")

        # Throttle to avoid rate limits
        if delay > 0 and i < len(queries):
            await asyncio.sleep(delay)

    total_time = time.time() - start_time

    # ═══════════════════════════════════════════════════════════════════════
    #  Summary Report
    # ═══════════════════════════════════════════════════════════════════════

    passed_count = sum(1 for r in results if r.get("pass"))
    keyword_count = sum(1 for r in results if r.get("keyword_match"))
    exclusion_count = sum(1 for r in results if r.get("exclusion_pass"))
    total = len(results)
    pct = (passed_count / total * 100) if total > 0 else 0
    kw_pct = (keyword_count / total * 100) if total > 0 else 0
    ex_pct = (exclusion_count / total * 100) if total > 0 else 0

    sep = "=" * 68
    print(f"\n{sep}")
    print(f"  EVAL RESULTS — variant: {variant}")
    print(sep)
    print(f"  Tool Match:       {passed_count}/{total} passed ({pct:.0f}%)")
    print(f"  Keyword Match:    {keyword_count}/{total} passed ({kw_pct:.0f}%)")
    print(f"  Exclusion Check:  {exclusion_count}/{total} passed ({ex_pct:.0f}%)")
    avg_t = total_time / total if total > 0 else 0
    print(f"  Total Time:       {total_time:.1f}s ({avg_t:.1f}s avg per query)")
    print(f"  Est. Cost:        ${total_cost:.4f}")
    print(sep)

    # ── Category breakdown ──
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

    # ── Difficulty breakdown ──
    diff_hdr = f"  {'Difficulty':<25} {'Pass':>6} {'Total':>6} {'Rate':>6}"
    print(f"\n{diff_hdr}")
    print(dash_line)
    for diff in ["easy", "medium", "hard"]:
        diff_results = [r for r in results if r.get("difficulty") == diff]
        if diff_results:
            diff_passed = sum(1 for r in diff_results if r.get("pass"))
            diff_total = len(diff_results)
            diff_pct = (diff_passed / diff_total * 100) if diff_total > 0 else 0
            print(
                f"  {diff:<25} {diff_passed:>6} {diff_total:>6}"
                f" {diff_pct:>5.0f}%"
            )

    # ── Stage 2: Coverage Matrix ──
    print_coverage_matrix(results)

    # ── Failed queries ──
    failed = [r for r in results if not r.get("pass")]
    if failed:
        print("\n  FAILED QUERIES:")
        for r in failed:
            error = f" -- {r['error']}" if "error" in r else ""
            print(f"  [{r['id']}] {r.get('query', '')[:55]}{error}")

    # ── Exclusion failures ──
    exclusion_fails = [
        r for r in results if not r.get("exclusion_pass", True)
    ]
    if exclusion_fails:
        print("\n  EXCLUSION VIOLATIONS (negative validation):")
        for r in exclusion_fails:
            print(f"  [{r['id']}] {r.get('query', '')[:55]}")

    print()

    # ── Write results to file ──
    if output_path:
        output = {
            "summary": {
                "variant": variant,
                "total": total,
                "passed": passed_count,
                "pass_rate": round(pct, 1),
                "keyword_match_rate": round(kw_pct, 1),
                "exclusion_pass_rate": round(ex_pct, 1),
                "total_time_seconds": round(total_time, 1),
                "avg_latency_seconds": round(avg_t, 1),
                "estimated_total_cost": round(total_cost, 4),
            },
            "results": results,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"  Results written to {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AgentForge eval suite")
    parser.add_argument(
        "--category",
        help="Filter by category (e.g. performance, portfolio_read)",
    )
    parser.add_argument(
        "--difficulty", choices=["easy", "medium", "hard"],
        help="Filter by difficulty",
    )
    parser.add_argument("--output", help="Write JSON results to file")
    parser.add_argument(
        "--delay", type=float, default=2.0,
        help="Seconds between queries to avoid rate limits (default 2.0)",
    )
    parser.add_argument(
        "--variant", default="baseline",
        help="Experiment variant name for A/B tracking (default: baseline)",
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
        variant=args.variant,
    ))
