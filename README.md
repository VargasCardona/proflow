# proflow

Discrete-event flow simulator inspired by ProModel. Define nodes and edges, spawn entities, and watch them flow through the system with a real-time pygame visualizer.

## Usage

```bash
python main.py
```

## Project Structure

- `main.py` — entry point, wires up a sample flow
- `model/flow.py` — simulation core (nodes, edges, entities, tick loop)
- `model/entities.py` — entity type exports
- `visualizer/engine.py` — pygame render loop
- `visualizer/layout.py` — node layout helpers

## Dependencies

- Python 3.10+
- pygame 2.5+

## Example

```python
from model.flow import Flow
from visualizer.engine import Engine

flow = Flow()
flow.add_node("source", x=100, y=300, throughput=2.0)
flow.add_node("proc1",  x=300, y=200, throughput=0.05)
flow.add_node("proc2",  x=500, y=400, throughput=1.1)
flow.add_node("sink",   x=900, y=300, throughput=999.0)

flow.add_edge("source", "proc1", transit_time=1.0)
flow.add_edge("proc1", "proc2",  transit_time=1.5)
flow.add_edge("proc2", "sink",   transit_time=1.0)

for _ in range(3):
    flow.spawn("source")

Engine(flow).run()
```
