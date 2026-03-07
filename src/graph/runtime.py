from __future__ import annotations

from typing import Any

from src.graph.state import HellyGraphState
from src.graph.types import StageGraphDefinition, GraphNode

try:  # pragma: no cover
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"
    StateGraph = None


class SequentialCompiledGraph:
    def __init__(self, *, node_order: list[str], nodes: dict[str, GraphNode]):
        self.node_order = list(node_order)
        self.nodes = dict(nodes)

    def invoke(self, state_input: dict[str, Any]) -> dict[str, Any]:
        state = HellyGraphState(**state_input)
        for node_name in self.node_order:
            state = self.nodes[node_name](state)
        return state.as_dict()


def _wrap_node(node: GraphNode):
    def _runner(state_input: dict[str, Any]) -> dict[str, Any]:
        state = HellyGraphState(**state_input)
        next_state = node(state)
        return next_state.as_dict()

    return _runner


def compile_stage_graph(*, definition: StageGraphDefinition, nodes: dict[str, GraphNode]):
    ordered_nodes = list(nodes.keys())
    if StateGraph is None:
        return SequentialCompiledGraph(node_order=ordered_nodes, nodes=nodes)

    builder = StateGraph(dict)
    for node_name, node in nodes.items():
        builder.add_node(node_name, _wrap_node(node))

    builder.set_entry_point(definition.entry_node_name)
    for index, node_name in enumerate(ordered_nodes):
        if index == len(ordered_nodes) - 1:
            builder.add_edge(node_name, END)
        else:
            builder.add_edge(node_name, ordered_nodes[index + 1])
    return builder.compile()

