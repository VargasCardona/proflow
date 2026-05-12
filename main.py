#!/usr/bin/env python3

import argparse
import random

from model.flow import Flow

NUM_RUNS = 5
RUN_DURATION = 480.0
SPAWN_INTERVAL_MEAN = 25.0
SERVICE_MEAN = 20.0
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


def build_flow() -> Flow:
    flow = Flow()

    flow.add_node(
        "fila",
        x=100,
        y=300,
        throughput=0.0,
        label="Queue",
        sprite="station.png",
        kind="queue",
    )
    flow.add_node(
        "mecanico",
        x=500,
        y=300,
        throughput=0.05,
        label="Proc A",
        sprite="station.png",
        capacity=1,
        service_dist=lambda: random.expovariate(1.0 / SERVICE_MEAN),
    )
    flow.add_node(
        "sink", x=900, y=300, throughput=999.0, label="Sink", sprite="station.png"
    )

    flow.add_edge("fila", "mecanico", transit_time=1.0)
    flow.add_edge("mecanico", "sink", transit_time=1.0)

    return flow


def setup_run(flow: Flow) -> None:
    flow.reset()
    # Generate exponential interarrival times
    current_time = 0.0
    while current_time < RUN_DURATION:
        flow.schedule_spawn("fila", current_time)
        current_time += random.expovariate(1.0 / SPAWN_INTERVAL_MEAN)


def run_headless(flow: Flow, num_runs: int, run_duration: float) -> list[dict]:
    """Run simulation without pygame visualization."""
    results: list[dict] = []
    for _ in range(num_runs):
        setup_run(flow)
        while flow.time < run_duration:
            remaining = run_duration - flow.time
            dt = min(1.0, remaining)
            flow.tick(dt)
        results.append(flow.get_metrics())
    return results


def print_node_summary(results: list[dict]) -> None:
    """Print per-node averages across all runs in Spanish format."""
    if not results or "nodes" not in results[0]:
        return

    node_order = ["fila", "mecanico", "sink"]
    display_names = {
        "fila": "Fila",
        "mecanico": "Mecánico",
        "sink": "Clientes atendidos",
    }
    capacities = {
        "fila": 999999.00,
        "mecanico": 1.00,
        "sink": 999999.00,
    }

    aggr: dict[str, dict[str, list[float]]] = {}
    for n in node_order:
        aggr[n] = {
            "entries": [],
            "avg_time_min": [],
            "avg_content": [],
            "max_content": [],
            "final_content": [],
            "utilization": [],
        }

    for r in results:
        final_time = r["final_time"]
        for name in node_order:
            nd = r["nodes"][name]
            aggr[name]["entries"].append(float(nd["entries"]))
            if nd["entries"] > 0:
                aggr[name]["avg_time_min"].append(nd["cumulative_time"] / nd["entries"])
            avg_cont = nd["content_area"] / final_time if final_time > 0 else 0.0
            aggr[name]["avg_content"].append(avg_cont)
            aggr[name]["max_content"].append(float(nd["content_max"]))
            aggr[name]["final_content"].append(float(nd["content_current"]))
            util = nd["busy_time"] / final_time * 100 if final_time > 0 else 0.0
            aggr[name]["utilization"].append(util)

    print()
    headers = [
        "Nombre",
        "Tiempo Programado (Min)",
        "Capacidad",
        "Total Entradas",
        "Tiempo Por Entrada Promedio (Sec)",
        "Contenido Promedio",
        "Contenido Máximo",
        "Contenido Actual",
        "% Utilización",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join([" --- " for _ in headers]) + "|")

    for name in node_order:
        avg_entries = sum(aggr[name]["entries"]) / len(aggr[name]["entries"])
        avg_time_sec = (
            sum(aggr[name]["avg_time_min"]) / len(aggr[name]["avg_time_min"]) * 60
            if aggr[name]["avg_time_min"]
            else 0.0
        )
        avg_content = sum(aggr[name]["avg_content"]) / len(aggr[name]["avg_content"])
        max_content = sum(aggr[name]["max_content"]) / len(aggr[name]["max_content"])
        final_content = sum(aggr[name]["final_content"]) / len(
            aggr[name]["final_content"]
        )
        avg_util = sum(aggr[name]["utilization"]) / len(aggr[name]["utilization"])

        def _fmt(val: float) -> str:
            s = f"{val:,.2f}"
            return s.replace(",", "_").replace(".", ",").replace("_", ".")

        row = [
            display_names[name],
            _fmt(RUN_DURATION),
            _fmt(capacities[name]),
            _fmt(avg_entries),
            _fmt(avg_time_sec),
            _fmt(avg_content),
            _fmt(max_content),
            _fmt(final_content),
            _fmt(avg_util),
        ]
        print("| " + " | ".join(row) + " |")


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
            f"{i:>4} {r['completed']:>10} {r['avg_time_in_system']:>10.2f} "
            f"{r['min_time_in_system']:>10.2f} {r['max_time_in_system']:>10.2f} "
            f"{r['final_time']:>12.2f}"
        )

    print("-" * 60)
    if results:
        completed_vals = [r["completed"] for r in results]
        avg_vals = [
            r["avg_time_in_system"] for r in results if r["avg_time_in_system"] > 0
        ]

        print(
            f"{'Avg':>4} {sum(completed_vals) / len(completed_vals):>10.2f} "
            f"{sum(avg_vals) / len(avg_vals) if avg_vals else 0.0:>10.2f}"
        )
    print("=" * 50)


def run_visual(flow: Flow) -> list[dict]:
    """Run with pygame visualization."""
    from visualizer.engine import Engine

    engine = Engine(
        flow,
        num_runs=NUM_RUNS,
        run_duration=RUN_DURATION,
        run_setup=setup_run,
        pause_between_runs=False,
        time_scale=1.0 / 60.0,  # pygame seconds -> simulation minutes
    )
    engine.run()
    return engine.results


def main() -> None:
    parser = argparse.ArgumentParser(description="promodel DES simulator")
    parser.add_argument(
        "--visual", action="store_true", help="run with pygame visualizer"
    )
    args = parser.parse_args()

    flow = build_flow()
    if args.visual:
        results = run_visual(flow)
    else:
        results = run_headless(flow, NUM_RUNS, RUN_DURATION)

    print_run_summary(results)
    print_node_summary(results)


if __name__ == "__main__":
    main()
