from __future__ import annotations

from dataclasses import dataclass, field

from model.flow import Flow


@dataclass(frozen=True)
class NodeLayout:
    x: int
    y: int
    label: str
    sprite: str | None = None


@dataclass
class Layout:
    nodes: dict[str, NodeLayout] = field(default_factory=dict)

    def set(self, name: str, x: int, y: int, label: str, sprite: str | None = None) -> None:
        self.nodes[name] = NodeLayout(x, y, label, sprite)

    def get(self, name: str) -> NodeLayout:
        return self.nodes[name]

    @classmethod
    def from_flow(cls, flow: Flow) -> Layout:
        l = cls()
        for name, data in flow.nodes.items():
            l.nodes[name] = NodeLayout(
                x=int(data["x"]),
                y=int(data["y"]),
                label=data.get("label", name),
                sprite=data.get("sprite"),
            )
        return l
