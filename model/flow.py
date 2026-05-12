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
        self._metrics: dict = {}
        self._reset_metrics()
        self._spawn_schedule: list[tuple[float, str]] = []
        self._schedule_index = 0

    def _reset_metrics(self) -> None:
        self._metrics = {
            "completed": 0,
            "completion_times": [],
            "times_in_system": [],
        }
        self._node_metrics = {}
        for name in self.nodes:
            self._init_node_metrics(name)

    def _init_node_metrics(self, name: str) -> None:
        self._node_metrics[name] = {
            "entries": 0,
            "cumulative_time": 0.0,
            "busy_time": 0.0,
            "content_area": 0.0,
            "content_max": 0,
        }

    def reset(self) -> None:
        """Reset simulation state while preserving topology."""
        for data in self.nodes.values():
            data["queue"] = []
            data["serving"] = None
            data["busy_until"] = 0.0
            data["_reserved"] = 0
        self.entities = []
        self._next_entity_id = 0
        self.time = 0.0
        self._reset_metrics()
        self._spawn_schedule.clear()
        self._schedule_index = 0

    def get_metrics(self) -> dict:
        """Return a snapshot of current run metrics."""
        completed = self._metrics["completed"]
        times = self._metrics["times_in_system"]

        node_snapshots = {}
        for name, nm in self._node_metrics.items():
            node_snapshots[name] = {
                "entries": nm["entries"],
                "cumulative_time": nm["cumulative_time"],
                "busy_time": nm["busy_time"],
                "content_area": nm["content_area"],
                "content_max": nm["content_max"],
                "content_current": self._node_content(name),
            }

        return {
            "completed": completed,
            "avg_time_in_system": sum(times) / len(times) if times else 0.0,
            "min_time_in_system": min(times) if times else 0.0,
            "max_time_in_system": max(times) if times else 0.0,
            "final_time": self.time,
            "nodes": node_snapshots,
        }

    # ------------------------------------------------------------------
    # builder API
    # ------------------------------------------------------------------

    def add_node(
        self,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
        throughput: float = 1.0,
        label: str | None = None,
        sprite: str | None = None,
        capacity: int = 0,
        service_dist: Callable[[], float] | None = None,
        kind: str = "process",
    ) -> None:
        self.nodes[name] = {
            "x": x,
            "y": y,
            "throughput": throughput,
            "queue": [],
            "serving": None,
            "label": label or name,
            "sprite": sprite,
            "busy_until": 0.0,
            "capacity": capacity,
            "service_dist": service_dist,
            "kind": kind,
            "_reserved": 0,
        }
        self._init_node_metrics(name)

    def add_edge(self, a: str, b: str, *, transit_time: float = 1.0) -> None:
        if a not in self.nodes or b not in self.nodes:
            raise KeyError(f"unknown node: {a} or {b}")
        self.edges[(a, b)] = {"transit_time": transit_time}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _accepts(self, node_name: str) -> bool:
        """Return True if node_name has spare capacity (accounts for in-transit entities)."""
        node = self.nodes[node_name]
        capacity = node.get("capacity", 0)
        if capacity == 0:
            return True
        occupied = len(node["queue"]) + node.get("_reserved", 0)
        if capacity == 1 and node.get("serving") is not None:
            occupied += 1
        return occupied < capacity

    def _start_transit(
        self, e: SimpleEntity, src: str, target: str, transit: float
    ) -> None:
        """Remove e from src queue and place it in transit toward target."""
        src_data = self.nodes[src]
        if e in src_data["queue"]:
            src_data["queue"].remove(e)
        e.current_node = None
        e.progress = 0.0
        if hasattr(e, "_node_enter_time"):
            del e._node_enter_time  # type: ignore[attr-defined]
        e._transit_target = target  # type: ignore[attr-defined]
        e._transit_src = src  # type: ignore[attr-defined]
        e._transit_time = transit  # type: ignore[attr-defined]
        e._transit_progress = 0.0  # type: ignore[attr-defined]
        self.nodes[target]["_reserved"] = self.nodes[target].get("_reserved", 0) + 1

    def _node_content(self, name: str) -> int:
        data = self.nodes[name]
        content = len(data["queue"])
        if data.get("capacity") == 1 and data.get("serving") is not None:
            content += 1
        return content

    # ------------------------------------------------------------------
    # simulation
    # ------------------------------------------------------------------

    def schedule_spawn(self, at: str, time: float) -> None:
        """Schedule an entity to spawn at `at` when simulation time reaches `time`."""
        self._spawn_schedule.append((time, at))

    def spawn(self, at: str) -> SimpleEntity:
        if at not in self.nodes:
            raise KeyError(f"unknown node: {at}")
        e = SimpleEntity(id=self._next_entity_id, current_node=at, progress=0.0)
        self._next_entity_id += 1
        self.entities.append(e)
        self.nodes[at]["queue"].append(e)
        e._node_enter_time = self.time  # type: ignore[attr-defined]
        e._spawn_time = self.time  # type: ignore[attr-defined]
        # Track entry for the node
        nm = self._node_metrics.get(at)
        if nm is not None:
            nm["entries"] += 1
        for cb in self._spawn_callbacks:
            cb(at, e)
        return e

    def _outgoing(self, node: str) -> list[tuple[str, float]]:
        return [
            (b, self.edges[(node, b)]["transit_time"])
            for (a, b) in self.edges
            if a == node
        ]

    def _start_service(self, name: str, entity: SimpleEntity) -> None:
        """Begin serving `entity` at single-server node `name`."""
        data = self.nodes[name]
        service_dist = data.get("service_dist")
        if service_dist is not None:
            service_time = service_dist()
        else:
            throughput = data["throughput"]
            service_time = 1.0 / throughput if throughput > 0 else float("inf")
        data["serving"] = entity
        data["busy_until"] = self.time + service_time

    def _depart(self, name: str, entity: SimpleEntity) -> None:
        """Move `entity` from node `name` into transit toward a downstream node."""
        outs = self._outgoing(name)
        if not outs:
            return
        target, transit = random.choice(outs)
        nm = self._node_metrics.get(name)
        if nm is not None:
            entered = getattr(entity, "_node_enter_time", self.time)
            nm["cumulative_time"] += self.time - entered
        entity.current_node = None
        entity.progress = 0.0
        if hasattr(entity, "_node_enter_time"):
            del entity._node_enter_time  # type: ignore[attr-defined]
        entity._transit_target = target  # type: ignore[attr-defined]
        entity._transit_src = name  # type: ignore[attr-defined]
        entity._transit_time = transit  # type: ignore[attr-defined]
        entity._transit_progress = 0.0  # type: ignore[attr-defined]
        self.nodes[target]["_reserved"] = self.nodes[target].get("_reserved", 0) + 1

    def tick(self, dt: float) -> None:
        """Advance simulation by dt seconds."""
        self.time += dt

        while self._schedule_index < len(self._spawn_schedule):
            sched_time, sched_node = self._spawn_schedule[self._schedule_index]
            if self.time >= sched_time:
                self.spawn(sched_node)
                self._schedule_index += 1
            else:
                break

        for e in self.entities:
            if not hasattr(e, "_transit_target"):
                continue
            e._transit_progress += dt  # type: ignore[attr-defined]
            total = e._transit_time  # type: ignore[attr-defined]
            e.progress = min(1.0, e._transit_progress / total)  # type: ignore[attr-defined]
            if e.progress < 1.0:
                continue

            # Arrival
            target = e._transit_target  # type: ignore[attr-defined]
            e.current_node = target
            e.progress = 0.0
            del e._transit_target  # type: ignore[attr-defined]
            del e._transit_time  # type: ignore[attr-defined]
            del e._transit_progress  # type: ignore[attr-defined]
            self.nodes[target]["_reserved"] = max(0, self.nodes[target].get("_reserved", 0) - 1)

            nm_tgt = self._node_metrics.get(target)
            if nm_tgt is not None:
                nm_tgt["entries"] += 1

            if target == "sink":
                spawn_time = getattr(e, "_spawn_time", self.time)
                self._metrics["completed"] += 1
                self._metrics["completion_times"].append(self.time)
                self._metrics["times_in_system"].append(self.time - spawn_time)
            else:
                e._node_enter_time = self.time  # type: ignore[attr-defined]
                self.nodes[target]["queue"].append(e)

        for name, data in self.nodes.items():
            nm = self._node_metrics.get(name)
            if nm is None:
                continue
            content = self._node_content(name)
            nm["content_area"] += content * dt
            if content > nm["content_max"]:
                nm["content_max"] = content

        # ── 4. Process nodes ────────────────────────────────────────────
        for name, data in self.nodes.items():
            outs = self._outgoing(name)
            if not outs:
                continue

            capacity = data.get("capacity", 0)
            nm = self._node_metrics.get(name)
            throughput = data["throughput"]

            if capacity == 1:
                # ── Single-server ──────────────────────────────────
                serving = data["serving"]

                # Track busy time only when actually serving
                if nm is not None and serving is not None:
                    nm["busy_time"] += dt

                # Check if current service is complete
                if serving is not None and self.time >= data["busy_until"]:
                    self._depart(name, serving)
                    data["serving"] = None
                    data["busy_until"] = 0.0
                    serving = None

                # If idle, try to start serving
                if serving is None:
                    queue = data["queue"]
                    if queue:
                        # Serve from own queue
                        e = queue.pop(0)
                        self._start_service(name, e)
                    else:
                        # Pull from upstream queues
                        for (a, b) in self.edges:
                            if b != name:
                                continue
                            up_queue = self.nodes[a]["queue"]
                            if not up_queue:
                                continue
                            if not self._accepts(name):
                                break
                            e = up_queue.pop(0)
                            self._start_transit(e, a, name, self.edges[(a, name)]["transit_time"])
                            nm_up = self._node_metrics.get(a)
                            if nm_up is not None:
                                entered = getattr(e, "_node_enter_time", self.time)
                                nm_up["cumulative_time"] += self.time - entered
                            break
            else:
                queue = data["queue"]

                if nm is not None and queue and throughput > 0:
                    nm["busy_time"] += dt

                if not queue:
                    continue

                service_time = 1.0 / throughput if throughput > 0 else float("inf")
                ready = []
                for e in queue:
                    entered = getattr(e, "_node_enter_time", self.time)
                    if self.time - entered >= service_time:
                        ready.append(e)

                for e in ready:
                    self._depart(name, e)
                    queue.remove(e)
