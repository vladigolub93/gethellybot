from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.graph.state import HellyGraphState


GraphNode = Callable[[HellyGraphState], HellyGraphState]


@dataclass(frozen=True)
class StageGraphDefinition:
    stage: str
    entry_node_name: str
    terminal_node_names: tuple[str, ...]

