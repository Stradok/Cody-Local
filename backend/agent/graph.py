from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import (
    planner_node,
    coding_node,
    filesystem_node,
    terminal_node,
    validation_node,
    review_node,
    step_router,
)

_ROUTING_MAP = {
    "coding":     "coding",
    "filesystem": "filesystem",
    "terminal":   "terminal",
    "validation": "validation",
    "review":     "review",
}


def build_agent() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner",    planner_node)
    graph.add_node("coding",     coding_node)
    graph.add_node("filesystem", filesystem_node)
    graph.add_node("terminal",   terminal_node)
    graph.add_node("validation", validation_node)
    graph.add_node("review",     review_node)

    graph.add_edge(START, "planner")

    # After planning, and after each specialist node, route to the correct next specialist (or review when done)
    for src in ["planner", "coding", "filesystem", "terminal", "validation"]:
        graph.add_conditional_edges(src, step_router, _ROUTING_MAP)

    graph.add_edge("review", END)

    return graph.compile()
