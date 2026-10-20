from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# 1. STATE — the shared notebook. Every node can read and update these fields.
class HelloState(TypedDict):
    name: str
    greeting: str
    shout: str
    count: int

# 2. NODES — plain functions. They get the state, and return ONLY the fields they change.
def greet_node(state: HelloState) -> dict:
    print("➡️  greet_node running, sees name =", state["name"])
    return {"greeting": f"Hello, {state['name']}!"}


def shout_node(state: HelloState) -> dict:
    print("➡️  shout_node running, sees greeting =", state["greeting"])
    return {"shout": state["greeting"].upper()}

def count_node(state: HelloState) -> dict:
    print("➡️  count_node running, sees name =", state["name"])
    return {"count": len(state["name"])}

# 3. GRAPH — register the nodes, then connect them with edges.
graph = StateGraph(HelloState)
graph.add_node("greet", greet_node)
graph.add_node("shout", shout_node)
graph.add_node("count", count_node)

graph.add_edge(START, "greet")   # start here
graph.add_edge("greet", "shout") # then this
graph.add_edge("shout", "count") # then this
graph.add_edge("count", END)     # then stop

app = graph.compile()

# 4. RUN IT — give the starting state, get the final state back.
result = app.invoke({"name": "Joel", "greeting": "", "shout": ""})
print("\nFinal state:", result)