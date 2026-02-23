"""Interactive CLI for chatting with the AgentForge Finance agent."""

from __future__ import annotations

import asyncio

from agent.core.agent import create_agent


async def main() -> None:
    """Run an interactive REPL with the finance agent."""
    print("=" * 60)
    print("  AgentForge Finance — Portfolio Intelligence Agent")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    agent = create_agent()
    thread_id = "cli-session"

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config={"configurable": {"thread_id": thread_id}},
            )

            messages = result.get("messages", [])
            if messages:
                final = messages[-1]
                content = final.content if hasattr(final, "content") else str(final)
                print(f"\nAgent: {content}\n")
            else:
                print("\nAgent: (no response)\n")

        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
