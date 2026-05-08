from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Protocol


class Entity(Protocol):
    id: int
    current_node: str | None
    progress: float
    color: tuple[int, int, int]


@dataclass
class SimpleEntity:
    id: int
    current_node: str | None = None
    progress: float = 0.0
    color: tuple[int, int, int] = field(default_factory=lambda: (0, 200, 255))


class Flow:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple[str, str], dict] = {}
        self.entities: list[SimpleEntity] = []
        self._next_entity_id = 0
        self.time = 0.0
        self._spawn_callbacks: list[Callable[[str, SimpleEntity], None]] = []

    # ------------------------------------------------------------------
    # builder API
    # ------------------------------------------------------------------

    def add_node(self, name: str, *, x: float = 0.0, y: float = 0.0, throughput: float = 1.0, label: str | None = None, sprite: str | None = None) -> None:
        self.nodes[name] = {"x": x, "y": y, "throughput": throughput, "queue": [], "label": label or name, "sprite": sprite, "busy_until": 0.0}

    def add_edge(self, a: str, b: str, *, transit_time: float = 1.0) -> None:
        if a not in self.nodes or b not in self.nodes:
            raise KeyError(f"unknown node: {a} or {b}")
        self.edges[(a, b)] = {"transit_time": transit_time}

    # ------------------------------------------------------------------
    # simulation
    # ------------------------------------------------------------------

    def spawn(self, at: str) -> SimpleEntity:
        if at not in self.nodes:
            raise KeyError(f"unknown node: {at}")
        e = SimpleEntity(id=self._next_entity_id, current_node=at, progress=0.0)
        self._next_entity_id += 1
        self.entities.append(e)
        self.nodes[at]["queue"].append(e)
        e._node_enter_time = self.time  # type: ignore[attr-defined]
        for cb in self._spawn_callbacks:
            cb(at, e)
        return e

    def _outgoing(self, node: str) -> list[tuple[str, float]]:
        return [(b, self.edges[(node, b)]["transit_time"]) for (a, b) in self.edges if a == node]

    def tick(self, dt: float) -> None:
        """Advance simulation by dt seconds."""
        self.time += dt
        print(self.nodes.items())

        for name, data in self.nodes.items():
            throughput = data["throughput"]
            queue = data["queue"]
            if not queue:
                continue

            service_time = 1.0 / throughput if throughput > 0 else float("inf")
            ready = []
            for e in queue:
                entered = getattr(e, "_node_enter_time", self.time)
                if self.time - entered >= service_time:
                    ready.append(e)

            for e in ready:
                outs = self._outgoing(name)
                if not outs:
                    continue
                target, transit = random.choice(outs)
                queue.remove(e)
                e.current_node = None
                e.progress = 0.0
                del e._node_enter_time  # type: ignore[attr-defined]
                e._transit_target = target  # type: ignore[attr-defined]
                e._transit_src = name  # type: ignore[attr-defined]
                e._transit_time = transit  # type: ignore[attr-defined]
                e._transit_progress = 0.0  # type: ignore[attr-defined]

        for e in self.entities:
            if hasattr(e, "_transit_target"):
                e._transit_progress += dt  # type: ignore[attr-defined]
                total = e._transit_time  # type: ignore[attr-defined]
                e.progress = min(1.0, e._transit_progress / total)  # type: ignore[attr-defined]
                if e.progress >= 1.0:
                    target = e._transit_target  # type: ignore[attr-defined]
                    e.current_node = target
                    e.progress = 0.0
                    self.nodes[target]["queue"].append(e)
                    e._node_enter_time = self.time  # type: ignore[attr-defined]
                    del e._transit_target  # type: ignore[attr-defined]
                    del e._transit_time  # type: ignore[attr-defined]
                    del e._transit_progress  # type: ignore[attr-defined]
