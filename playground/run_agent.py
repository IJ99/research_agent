from app.graph import agent

initial_state = {
    "topic": "How AI is used to detect fraud in African fintech",
    "search_queries": [],
    "search_results": [],
    "report_draft": "",
    "critique": "",
    "iteration": 0,
    "is_satisfactory": False,
}

final_state = agent.invoke(initial_state)

# Save the report so you can read it nicely
with open("report.md", "w", encoding="utf-8") as f:
    f.write(final_state["report_draft"])

print("\n✅ Done! Report saved to report.md")

print(f"Rounds used: {final_state['iteration']}")
print(f"Approved by critic: {final_state['is_satisfactory']}")