#!/usr/bin/env python3

from model.flow import Flow
from visualizer.engine import Engine


def main() -> None:
    flow = Flow()

    flow.add_node("source", x=100, y=300, throughput=2.0, label="Source", sprite="station.png")
    flow.add_node("proc1", x=300, y=200, throughput=0.05, label="Proc A", sprite="station.png")
    flow.add_node("proc2", x=500, y=400, throughput=1.1, label="Proc B", sprite="station.png")
    flow.add_node("sink", x=900, y=300, throughput=999.0, label="Sink", sprite="station.png")

    flow.add_edge("source", "proc1", transit_time=1.0)
    flow.add_edge("proc1", "proc2", transit_time=1.5)
    flow.add_edge("proc2", "sink", transit_time=1.0)

    for _ in range(3):
        flow.spawn("source")

    engine = Engine(flow)
    engine.run()


if __name__ == "__main__":
    main()
