#!/usr/bin/env python3

from model.flow import Flow
from visualizer.engine import Engine

# Simulation constants
NUM_RUNS = 5
RUN_DURATION = 30.0
PAUSE_BETWEEN_RUNS = False


def build_flow() -> Flow:
    flow = Flow()

    flow.add_node(
        "source", x=100, y=300, throughput=2.0, label="Source", sprite="station.png"
    )
    flow.add_node(
        "proc1", x=300, y=200, throughput=0.05, label="Proc A", sprite="station.png"
    )
    flow.add_node(
        "proc2", x=500, y=400, throughput=1.1, label="Proc B", sprite="station.png"
    )
    flow.add_node(
        "sink", x=900, y=300, throughput=999.0, label="Sink", sprite="station.png"
    )

    flow.add_edge("source", "proc1", transit_time=1.0)
    flow.add_edge("proc1", "proc2", transit_time=1.5)
    flow.add_edge("proc2", "sink", transit_time=1.0)

    return flow


def setup_run(flow: Flow) -> None:
    flow.reset()
    for _ in range(3):
        flow.spawn("source")


def print_run_summary(results: list[dict]) -> None:
    print("\n" + "=" * 50)
    print("RUN SUMMARY")
    print("=" * 50)

    headers = ["Run", "Completed", "Avg Time", "Min Time", "Max Time", "Final Time"]
    print(
        f"{headers[0]:>4} {headers[1]:>10} {headers[2]:>10} {headers[3]:>10} {headers[4]:>10} {headers[5]:>12}"
    )
    print("-" * 60)

    for i, r in enumerate(results, start=1):
        print(
            f"{i:>4} {r['completed']:>10} {r['avg_time_in_system']:>10.2f} {r['min_time_in_system']:>10.2f} {r['max_time_in_system']:>10.2f} {r['final_time']:>12.2f}"
        )

    print("-" * 60)
    completed_vals = [r["completed"] for r in results]
    avg_vals = [r["avg_time_in_system"] for r in results if r["avg_time_in_system"] > 0]

    print(
        f"{'Avg':>4} {sum(completed_vals) / len(completed_vals):>10.2f} "
        f"{sum(avg_vals) / len(avg_vals) if avg_vals else 0.0:>10.2f}"
    )
    print("=" * 50)


def main() -> None:
    flow = build_flow()

    engine = Engine(
        flow,
        num_runs=NUM_RUNS,
        run_duration=RUN_DURATION,
        run_setup=setup_run,
        pause_between_runs=PAUSE_BETWEEN_RUNS,
    )
    engine.run()

    print_run_summary(engine.results)


if __name__ == "__main__":
    main()
