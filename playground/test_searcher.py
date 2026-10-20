from app.nodes import planner_node, searcher_node

# Start with a whiteboard that only has a topic
state = {"topic": "How AI is used to detect fraud in African fintech", "search_results": []}

# Run the planner, then merge its update into the whiteboard (by hand, for now)
state.update(planner_node(state))

# Run the searcher on the updated whiteboard
update = searcher_node(state)

# Peek at the first result
print("\n--- First result ---")
print(update["search_results"][0])