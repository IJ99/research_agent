from langgraph.graph import StateGraph, START, END

from app.state import ResearchState
from app.nodes import planner_node, searcher_node, writer_node, critic_node, cleanup_node

MAX_ROUNDS = 3


def should_continue(state: ResearchState) -> str:
    """The manager's decision after the critic speaks."""
    if state["is_satisfactory"]:
        return "done"
    if state["iteration"] >= MAX_ROUNDS:
        print(f"⏹️  Hit {MAX_ROUNDS} rounds — cleaning up remaining flagged claims.")
        return "cleanup"
    return "search_again"


workflow = StateGraph(ResearchState)

workflow.add_node("planner", planner_node)
workflow.add_node("searcher", searcher_node)
workflow.add_node("writer", writer_node)
workflow.add_node("critic", critic_node)
workflow.add_node("cleanup", cleanup_node)

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "searcher")
workflow.add_edge("searcher", "writer")
workflow.add_edge("writer", "critic")

workflow.add_conditional_edges(
    "critic",
    should_continue,
    {
        "done": END,                   # approved → finish
        "search_again": "searcher",    # not approved, rounds left → loop
        "cleanup": "cleanup",          # not approved, out of rounds → clean up
    },
)
workflow.add_edge("cleanup", END)

agent = workflow.compile()