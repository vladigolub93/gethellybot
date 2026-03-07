from __future__ import annotations

from dataclasses import dataclass, field

from src.graph.types import GraphNode, StageGraphDefinition


@dataclass
class StageGraphRegistry:
    definitions: dict[str, StageGraphDefinition] = field(default_factory=dict)
    node_builders: dict[str, dict[str, GraphNode]] = field(default_factory=dict)

    def register_stage(
        self,
        *,
        definition: StageGraphDefinition,
        nodes: dict[str, GraphNode],
    ) -> None:
        self.definitions[definition.stage] = definition
        self.node_builders[definition.stage] = dict(nodes)

    def get_definition(self, stage: str) -> StageGraphDefinition | None:
        return self.definitions.get(stage)

    def get_nodes(self, stage: str) -> dict[str, GraphNode]:
        return dict(self.node_builders.get(stage, {}))


registry = StageGraphRegistry()

